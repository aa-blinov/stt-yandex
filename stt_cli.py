#!/usr/bin/env python3
"""
Speech-to-Text CLI Tool

A comprehensive CLI tool that combines audio conversion and speech transcription
using Yandex Cloud Speech-to-Text API.
"""

import json
import os
import time
import traceback
from pathlib import Path
from typing import Optional

import boto3
import requests
import typer
import urllib3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv, set_key
from pydub import AudioSegment
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


console = Console()
app = typer.Typer(
    name="stt-cli",
    help="Speech-to-Text CLI tool with automatic audio conversion and Yandex Cloud STT integration",
    rich_markup_mode="rich",
)

# Configuration file path
ENV_FILE = Path(".env")


class Config:
    """Configuration manager for environment variables"""

    def __init__(self):
        self.api_key: Optional[str] = None
        self.folder_id: Optional[str] = None
        self.bucket_name: Optional[str] = None
        self.access_key_id: Optional[str] = None
        self.secret_access_key: Optional[str] = None
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from .env file"""
        if ENV_FILE.exists():
            load_dotenv(ENV_FILE)
            self.api_key = os.getenv("YANDEX_API_KEY")
            self.folder_id = os.getenv("YANDEX_FOLDER_ID")
            self.bucket_name = os.getenv("YANDEX_BUCKET_NAME")
            self.access_key_id = os.getenv("YANDEX_ACCESS_KEY_ID")
            self.secret_access_key = os.getenv("YANDEX_SECRET_ACCESS_KEY")

    def is_configured(self) -> bool:
        """Check if all required configuration is present"""
        return all([self.api_key, self.folder_id, self.bucket_name])

    def is_upload_configured(self) -> bool:
        """Check if upload configuration is present"""
        return all([self.access_key_id, self.secret_access_key, self.bucket_name])

    def save_config(
        self,
        api_key: str,
        folder_id: str,
        bucket_name: str,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ) -> None:
        """Save configuration to .env file"""
        ENV_FILE.touch(exist_ok=True)
        set_key(ENV_FILE, "YANDEX_API_KEY", api_key)
        set_key(ENV_FILE, "YANDEX_FOLDER_ID", folder_id)
        set_key(ENV_FILE, "YANDEX_BUCKET_NAME", bucket_name)

        # Save Object Storage credentials if provided
        if access_key_id:
            set_key(ENV_FILE, "YANDEX_ACCESS_KEY_ID", access_key_id)
        if secret_access_key:
            set_key(ENV_FILE, "YANDEX_SECRET_ACCESS_KEY", secret_access_key)

        self.load_config()


def convert_to_mono(input_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Check audio channels and convert to mono if necessary.
    Saves converted files to 'mono/' directory.

    Args:
        input_path: Path to input audio file
        output_path: Path to output file (optional)

    Returns:
        Path to the mono audio file (original if already mono, converted if stereo)
    """
    try:
        # Create mono directory if it doesn't exist
        mono_dir = input_path.parent / "mono"
        mono_dir.mkdir(exist_ok=True)

        # Check if mono version already exists
        if output_path is None:
            output_path = mono_dir / f"{input_path.stem}_mono.ogg"

        # If mono file already exists, use it
        if output_path.exists():
            console.print(f"[green]✓ Using existing mono file:[/green] {output_path}")
            return output_path

        # Get file size for logging
        file_size = input_path.stat().st_size / (1024 * 1024)  # MB
        console.print(
            f"[blue]Loading audio file:[/blue] {input_path} ({file_size:.1f} MB)"
        )

        # Load with optimized settings for faster processing
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            load_task = progress.add_task("Loading audio file...", total=None)
            audio = AudioSegment.from_file(input_path)
            progress.remove_task(load_task)

        console.print(
            f"[cyan]Audio info:[/cyan] {audio.channels} channels, {len(audio) / 1000:.1f}s, {audio.frame_rate}Hz"
        )

        if audio.channels == 1:
            console.print(
                "[green]✓ Audio is already mono, no conversion needed[/green]"
            )
            return input_path

        # Step 2: Convert to mono
        console.print(
            f"[yellow]Converting {audio.channels}-channel audio to mono...[/yellow]"
        )
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            convert_task = progress.add_task("Converting to mono...", total=None)
            mono_audio = audio.set_channels(1)
            progress.remove_task(convert_task)

        # Step 3: Export to mono directory
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            export_task = progress.add_task("Saving mono audio...", total=None)

            # Export with optimized settings for faster processing
            mono_audio.export(
                output_path,
                format="ogg",
                parameters=[
                    "-c:a",
                    "libopus",  # Use Opus codec for better compression
                    "-b:a",
                    "64k",  # Lower bitrate for faster processing
                    "-application",
                    "voip",  # Optimize for speech
                ],
            )
            progress.remove_task(export_task)

        output_size = output_path.stat().st_size / (1024 * 1024)  # MB
        console.print(
            f"[green]✓ Mono audio saved:[/green] {output_path} ({output_size:.1f} MB)"
        )
        console.print(f"[dim]Compression ratio: {file_size / output_size:.1f}x[/dim]")

        return output_path

    except Exception as e:
        console.print(f"[red]Error during audio conversion:[/red] {e}")
        raise


def upload_to_object_storage(config: Config, file_path: Path, object_key: str) -> bool:
    """
    Upload file to Yandex Object Storage using boto3 S3-compatible client

    Args:
        config: Configuration object with access keys
        file_path: Path to local file to upload
        object_key: Key (path) for the object in storage

    Returns:
        True if upload successful, False otherwise
    """
    if not config.is_upload_configured():
        console.print("[red]Upload configuration is incomplete![/red]")
        console.print("Please configure access keys with: [bold]stt-cli config[/bold]")
        return False

    try:
        # Create S3 client for Yandex Object Storage
        s3_client = boto3.client(
            "s3",
            endpoint_url="https://storage.yandexcloud.net",
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name="ru-central1",  # Yandex Cloud region
        )

        # Determine content type
        content_type = "audio/ogg"  # Default for audio files
        if file_path.suffix.lower() == ".mp3":
            content_type = "audio/mpeg"
        elif file_path.suffix.lower() == ".wav":
            content_type = "audio/wav"
        elif file_path.suffix.lower() == ".m4a":
            content_type = "audio/mp4"

        console.print(f"[blue]Uploading file to Object Storage:[/blue] {object_key}")

        # Upload file with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            upload_task = progress.add_task(
                "Uploading to Object Storage...", total=None
            )

            # Upload file
            s3_client.upload_file(
                str(file_path),
                config.bucket_name,
                object_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "ACL": "private",  # Keep files private
                },
            )

            progress.remove_task(upload_task)

        console.print("[green]✓ File uploaded successfully![/green]")
        return True

    except NoCredentialsError:
        console.print("[red]AWS credentials not found or invalid![/red]")
        console.print("Please check your access keys in the configuration.")
        return False
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        console.print(f"[red]Upload failed [{error_code}]:[/red] {error_message}")

        if error_code == "NoSuchBucket":
            console.print(
                f"[yellow]Bucket '{config.bucket_name}' does not exist or is not accessible.[/yellow]"
            )
        elif error_code == "AccessDenied":
            console.print(
                "[yellow]Access denied. Check your credentials and bucket permissions.[/yellow]"
            )

        return False
    except Exception as e:
        console.print(f"[red]Upload error:[/red] {e}")
        return False


def check_file_exists_in_storage(config: Config, object_key: str) -> bool:
    """
    Check if file already exists in Yandex Object Storage

    Args:
        config: Configuration object with access keys
        object_key: Key (path) for the object in storage

    Returns:
        True if file exists, False otherwise
    """
    if not config.is_upload_configured():
        # If upload is not configured, we can't check - assume file doesn't exist
        return False

    try:
        # Create S3 client for Yandex Object Storage
        s3_client = boto3.client(
            "s3",
            endpoint_url="https://storage.yandexcloud.net",
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name="ru-central1",
        )

        # Try to get object metadata (head_object is faster than get_object)
        s3_client.head_object(Bucket=config.bucket_name, Key=object_key)
        return True

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            # File doesn't exist - this is what we want
            return False
        else:
            # Other error - log it but assume file doesn't exist
            console.print(
                f"[yellow]Warning: Could not check file existence [{error_code}]: {e.response['Error']['Message']}[/yellow]"
            )
            return False
    except Exception as e:
        # Any other error - assume file doesn't exist
        console.print(f"[yellow]Warning: Could not check file existence: {e}[/yellow]")
        return False


def pretty_api_error(response: requests.Response) -> str:
    """Format API error response for better readability"""
    try:
        data = response.json()
    except Exception:
        return response.text

    if "error" in data:
        err = data["error"]
        # Handle case where error might be a string instead of object
        if isinstance(err, dict):
            code = err.get("code", "unknown")
            msg = err.get("message", "no message")
            details = err.get("details", [])
            return f"API Error [{code}]: {msg}\nDetails: {json.dumps(details, ensure_ascii=False, indent=2)}"
        else:
            # Error is a string
            return f"API Error: {err}"
    return json.dumps(data, ensure_ascii=False, indent=2)


def transcribe_audio(config: Config, file_path: str) -> tuple[str, str, str]:
    """
    Transcribe audio file using Yandex Cloud STT API

    Args:
        config: Configuration object with API credentials
        file_path: Path to the audio file in Yandex Cloud Storage

    Returns:
        Tuple of (clean_text, srt_content, raw_json_response)
    """
    file_uri = f"https://storage.yandexcloud.net/{config.bucket_name}/{file_path}"

    request_data = {
        "uri": file_uri,
        "recognitionModel": {
            "model": "general",
            "audioFormat": {"containerAudio": {"containerAudioType": "OGG_OPUS"}},
            "languageRestriction": {
                "restrictionType": "WHITELIST",
                "languageCode": ["ru-RU"],
            },
            "textNormalization": {
                "textNormalization": "TEXT_NORMALIZATION_ENABLED",
                "phoneFormattingMode": "PHONE_FORMATTING_MODE_DISABLED",
                "profanityFilter": False,
                "literatureText": True,
            },
        },
        "speakerLabeling": {"speakerLabeling": "SPEAKER_LABELING_ENABLED"},
    }

    headers = {
        "Authorization": f"Api-key {config.api_key}",
        "x-folder-id": config.folder_id,
    }

    # Start transcription
    console.print("[blue]Starting transcription request...[/blue]")
    response = requests.post(
        "https://stt.api.cloud.yandex.net/stt/v3/recognizeFileAsync",
        headers=headers,
        json=request_data,
        verify=False,
    )

    if response.status_code != 200:
        error_msg = f"Recognition request failed: {response.status_code}\n{pretty_api_error(response)}"
        console.print(f"[red]{error_msg}[/red]")
        raise typer.Exit(1)

    operation_data = response.json()
    operation_id = operation_data.get("id")
    if not operation_id:
        console.print("[red]Operation ID not found in response[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Operation ID:[/green] {operation_id}")

    operation_url = f"https://operation.api.cloud.yandex.net/operations/{operation_id}"

    # Wait for completion with progress indicator
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Waiting for transcription to complete...", total=None)

        while True:
            op_response = requests.get(operation_url, headers=headers, verify=False)

            if op_response.status_code != 200:
                console.print(
                    f"[red]Operation check failed: {op_response.status_code}[/red]"
                )
                console.print(pretty_api_error(op_response))
                time.sleep(10)
                continue

            op_data = op_response.json()

            if op_data.get("done"):
                if "error" in op_data:
                    error_msg = f"Operation failed:\n{json.dumps(op_data['error'], ensure_ascii=False, indent=2)}"
                    console.print(f"[red]{error_msg}[/red]")
                    raise typer.Exit(1)
                break

            time.sleep(10)

    # Get transcription result
    console.print("[blue]Retrieving transcription result...[/blue]")
    speech_response = requests.get(
        f"https://stt.api.cloud.yandex.net/stt/v3/getRecognition?operation_id={operation_id}",
        headers=headers,
        verify=False,
    )

    if speech_response.status_code != 200:
        error_msg = f"Result request failed: {speech_response.status_code}\n{pretty_api_error(speech_response)}"
        console.print(f"[red]{error_msg}[/red]")
        raise typer.Exit(1)

    # Parse streaming JSON response and extract text with speaker information and timestamps
    try:
        response_text = speech_response.text
        segments = []  # List to store segments with timing and speaker info

        # Process each line of the streaming response
        for line in response_text.strip().split("\n"):
            if line.strip():
                try:
                    result_data = json.loads(line)

                    # Extract text from finalRefinement (normalized text) or final alternatives
                    if "result" in result_data:
                        result = result_data["result"]
                        channel_tag = result.get("channelTag", "0")

                        # Prefer finalRefinement for better text normalization
                        if (
                            "finalRefinement" in result
                            and "normalizedText" in result["finalRefinement"]
                        ):
                            normalized = result["finalRefinement"]["normalizedText"]
                            if (
                                "alternatives" in normalized
                                and normalized["alternatives"]
                            ):
                                alt = normalized["alternatives"][0]
                                text = alt.get("text", "")
                                start_time = alt.get("startTimeMs", 0)
                                end_time = alt.get("endTimeMs", 0)

                                # Convert string timestamps to int if needed
                                try:
                                    start_time = int(start_time) if start_time else 0
                                    end_time = int(end_time) if end_time else 0
                                except (ValueError, TypeError):
                                    start_time = 0
                                    end_time = 0

                                if text.strip():
                                    segments.append(
                                        {
                                            "text": text,
                                            "start_time": start_time,
                                            "end_time": end_time,
                                            "speaker": int(channel_tag) + 1,
                                        }
                                    )

                        # Fallback to regular final alternatives
                        elif "final" in result and "alternatives" in result["final"]:
                            alternatives = result["final"]["alternatives"]
                            if alternatives:
                                alt = alternatives[0]
                                text = alt.get("text", "")
                                start_time = alt.get("startTimeMs", 0)
                                end_time = alt.get("endTimeMs", 0)

                                # Convert string timestamps to int if needed
                                try:
                                    start_time = int(start_time) if start_time else 0
                                    end_time = int(end_time) if end_time else 0
                                except (ValueError, TypeError):
                                    start_time = 0
                                    end_time = 0

                                if text.strip():
                                    segments.append(
                                        {
                                            "text": text,
                                            "start_time": start_time,
                                            "end_time": end_time,
                                            "speaker": int(channel_tag) + 1,
                                        }
                                    )

                except json.JSONDecodeError:
                    continue  # Skip malformed JSON lines

        # Remove duplicates based on time and speaker, prefer normalized text
        unique_segments = []
        seen_segments = {}  # key: (start_time, end_time, speaker), value: segment

        for segment in segments:
            segment_key = (
                segment["start_time"],
                segment["end_time"],
                segment["speaker"],
            )

            if segment_key not in seen_segments:
                # First occurrence of this time/speaker combination
                seen_segments[segment_key] = segment
            else:
                # Duplicate found - prefer the one with better formatting (capitalized, punctuation)
                existing = seen_segments[segment_key]
                current = segment

                # Prefer text that starts with capital letter or has punctuation
                existing_score = 0
                current_score = 0

                if existing["text"] and existing["text"][0].isupper():
                    existing_score += 1
                if current["text"] and current["text"][0].isupper():
                    current_score += 1

                if existing["text"].endswith((".", "!", "?")):
                    existing_score += 1
                if current["text"].endswith((".", "!", "?")):
                    current_score += 1

                # Replace if current segment has better formatting
                if current_score > existing_score:
                    seen_segments[segment_key] = current

        unique_segments = list(seen_segments.values())

        unique_segments.sort(key=lambda x: x["start_time"])

        # Format clean text output
        if unique_segments:
            formatted_text = []
            current_speaker = None
            current_text = []

            for segment in unique_segments:
                if current_speaker != segment["speaker"]:
                    if current_text:
                        formatted_text.append(
                            f"Спикер {current_speaker}: {' '.join(current_text)}"
                        )
                    current_speaker = segment["speaker"]
                    current_text = [segment["text"]]
                else:
                    current_text.append(segment["text"])

            # Add the last speaker's text
            if current_text:
                formatted_text.append(
                    f"Спикер {current_speaker}: {' '.join(current_text)}"
                )

            clean_text = "\n\n".join(formatted_text)
        else:
            clean_text = "No text found in response"

        # Generate SRT content
        srt_content = generate_srt(unique_segments)

        return clean_text, srt_content, response_text

    except Exception as e:
        console.print(f"[red]Error parsing response:[/red] {e}")
        return f"Error parsing response: {e}", "", speech_response.text


def generate_srt(segments: list) -> str:
    """Generate SRT subtitle content from segments"""
    if not segments:
        return ""

    srt_lines = []

    for i, segment in enumerate(segments, 1):
        # Convert milliseconds to SRT time format (HH:MM:SS,mmm)
        start_time = ms_to_srt_time(segment["start_time"])
        end_time = ms_to_srt_time(segment["end_time"])

        # SRT format: sequence number, time range, text, blank line
        srt_lines.append(str(i))
        srt_lines.append(f"{start_time} --> {end_time}")
        srt_lines.append(f"Спикер {segment['speaker']}: {segment['text']}")
        srt_lines.append("")  # Blank line between subtitles

    return "\n".join(srt_lines)


def ms_to_srt_time(milliseconds) -> str:
    """Convert milliseconds to SRT time format (HH:MM:SS,mmm)"""
    # Handle string input and convert to int
    if isinstance(milliseconds, str):
        try:
            milliseconds = int(milliseconds)
        except ValueError:
            milliseconds = 0
    elif milliseconds is None:
        milliseconds = 0

    total_seconds = milliseconds // 1000
    ms = milliseconds % 1000

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


@app.command()
def config(
    api_key: Optional[str] = typer.Option(
        None, "--api-key", help="Yandex Cloud API key"
    ),
    folder_id: Optional[str] = typer.Option(
        None, "--folder-id", help="Yandex Cloud folder ID"
    ),
    bucket_name: Optional[str] = typer.Option(
        None, "--bucket-name", help="Yandex Cloud Storage bucket name"
    ),
    access_key_id: Optional[str] = typer.Option(
        None, "--access-key-id", help="Object Storage access key ID"
    ),
    secret_access_key: Optional[str] = typer.Option(
        None, "--secret-access-key", help="Object Storage secret access key"
    ),
    setup_upload: bool = typer.Option(
        False, "--setup-upload", help="Configure Object Storage upload credentials"
    ),
):
    """Configure Yandex Cloud credentials and settings"""

    config_obj = Config()

    console.print(
        Panel.fit(
            "[bold blue]Yandex Cloud STT Configuration[/bold blue]\n\n"
            "Please provide your Yandex Cloud credentials.\n"
            "See README.md for detailed instructions on how to get these values.",
            title="Configuration Setup",
        )
    )

    # Basic STT configuration
    if not config_obj.api_key:
        console.print(
            "\n[cyan]API Key:[/cyan] Create a service account in Yandex Cloud Console → IAM → Service accounts"
        )
        console.print(
            "Assign role: ai.speechkit-stt.user (required for speech recognition)"
        )
        console.print("Then create an API key for this service account")

    api_key = api_key or Prompt.ask(
        "Enter your Yandex Cloud API key", default=config_obj.api_key or ""
    )

    if not config_obj.folder_id:
        console.print(
            "\n[cyan]Folder ID:[/cyan] Found in Yandex Cloud Console URL or in folder settings"
        )
        console.print("Example: b1g2345abcde67890fgh")

    folder_id = folder_id or Prompt.ask(
        "Enter your Yandex Cloud folder ID", default=config_obj.folder_id or ""
    )

    if not config_obj.bucket_name:
        console.print(
            "\n[cyan]Bucket Name:[/cyan] Create a bucket in Object Storage service"
        )
        console.print("This is where your audio files should be stored")

    bucket_name = bucket_name or Prompt.ask(
        "Enter your Yandex Cloud Storage bucket name",
        default=config_obj.bucket_name or "",
    )

    if not all([api_key, folder_id, bucket_name]):
        console.print("[red]All basic configuration parameters are required[/red]")
        raise typer.Exit(1)

    # Object Storage configuration (optional but recommended)
    storage_access_key_id = access_key_id
    storage_secret_access_key = secret_access_key

    if not config_obj.is_upload_configured() or setup_upload:
        console.print("\n" + "=" * 60)
        console.print(
            "[bold yellow]Object Storage Configuration (Optional)[/bold yellow]"
        )
        console.print(
            "Configure these to enable automatic file upload to Object Storage."
        )
        console.print("Without these, you'll need to upload files manually.")

        setup_storage = setup_upload or Confirm.ask(
            "\nWould you like to configure Object Storage upload credentials?",
            default=True,
        )

        if setup_storage:
            console.print("\n[cyan]Object Storage Access Keys:[/cyan]")
            console.print("1. Create a service account with 'storage.editor' role")
            console.print("2. Generate static access keys for this service account")
            console.print("3. These are DIFFERENT from your API key above")

            storage_access_key_id = storage_access_key_id or Prompt.ask(
                "Enter Object Storage Access Key ID",
                default=config_obj.access_key_id or "",
            )

            storage_secret_access_key = storage_secret_access_key or Prompt.ask(
                "Enter Object Storage Secret Access Key",
                default=config_obj.secret_access_key or "",
                password=True,
            )

    # Save configuration
    config_obj.save_config(
        api_key,
        folder_id,
        bucket_name,
        storage_access_key_id,
        storage_secret_access_key,
    )

    console.print("\n[green]✓ Configuration saved successfully![/green]")

    if storage_access_key_id and storage_secret_access_key:
        console.print("[green]✓ Object Storage upload is configured[/green]")
    else:
        console.print(
            "[yellow]⚠ Object Storage upload not configured - files will need to be uploaded manually[/yellow]"
        )


@app.command()
def transcribe(
    input_file: Optional[Path] = typer.Argument(None, help="Path to input audio file"),
    cloud_path: Optional[str] = typer.Argument(
        None, help="Path to file in Yandex Cloud Storage (without bucket name)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output SRT file for transcription result"
    ),
    save_json: bool = typer.Option(
        True, "--save-json/--no-save-json", help="Save raw JSON response"
    ),
):
    """Transcribe audio file using Yandex Cloud STT"""

    # Load configuration
    config_obj = Config()
    if not config_obj.is_configured():
        console.print(
            Panel.fit(
                "[red]Configuration is incomplete![/red]\n\n"
                "Please run [bold]stt-cli config[/bold] to set up your credentials.",
                title="Configuration Required",
            )
        )
        raise typer.Exit(1)

    # Interactive mode: prompt for missing parameters
    interactive_mode = False
    if input_file is None:
        while True:
            input_file_str = Prompt.ask("Enter path to input audio file")
            input_file = Path(input_file_str)
            if input_file.exists():
                break
            else:
                console.print(f"[red]File not found:[/red] {input_file}")
                console.print("Please check the path and try again.")
        interactive_mode = True

    if cloud_path is None:
        # Use filename in root by default
        suggested_path = input_file.name if input_file else "audio.ogg"

        # Only prompt if we're in interactive mode (no input_file was provided)
        if input_file is None:
            console.print(
                f"[dim]Press Enter to use '{suggested_path}' in bucket root, or type custom path[/dim]"
            )
            cloud_path = Prompt.ask(
                "Enter path to file in Yandex Cloud Storage (without bucket name)",
                default=suggested_path,
            )
            interactive_mode = True
        else:
            # Non-interactive mode: use the input filename automatically
            cloud_path = suggested_path

    # Generate output filename if not specified
    if output_file is None:
        if input_file:
            base_name = input_file.stem
        else:
            base_name = "transcription"
        console.print(
            f"[cyan]Files will be saved to outputs/ directory as '{base_name}.*'[/cyan]"
        )

    # Always convert to mono - Yandex SpeechKit requires mono audio
    # File existence already checked in interactive mode or will be checked here
    if not input_file.exists():
        console.print(f"[red]Input file not found:[/red] {input_file}")
        raise typer.Exit(1)

    # Check if file already exists in Object Storage before processing
    if config_obj.is_upload_configured():
        console.print(
            "[blue]Checking if file already exists in Object Storage...[/blue]"
        )
        if check_file_exists_in_storage(config_obj, cloud_path):
            console.print(
                Panel.fit(
                    f"[red]File already exists in Object Storage![/red]\n\n"
                    f"File: [bold]{cloud_path}[/bold]\n"
                    f"Bucket: [bold]{config_obj.bucket_name}[/bold]\n\n"
                    f"To avoid overwriting existing files, the script will exit.\n"
                    f"Please use a different filename or remove the existing file first.",
                    title="File Already Exists",
                )
            )
            raise typer.Exit(1)
        console.print(
            "[green]✓ File does not exist in Object Storage, proceeding...[/green]"
        )

    # Always convert to mono (required by Yandex SpeechKit)
    processed_file = convert_to_mono(input_file)

    # Upload processed file to Object Storage if configured
    if config_obj.is_upload_configured():
        console.print(
            f"[blue]Uploading {processed_file.name} to Object Storage...[/blue]"
        )
        if upload_to_object_storage(config_obj, processed_file, cloud_path):
            console.print(
                f"[green]✓ File uploaded to {config_obj.bucket_name}/{cloud_path}[/green]"
            )
        else:
            console.print("[red]Upload failed! Please upload the file manually.[/red]")
            console.print(
                f"[cyan]Upload {processed_file.name} to Object Storage bucket {config_obj.bucket_name}[/cyan]"
            )
            raise typer.Exit(1)
    else:
        console.print(
            f"[yellow]⚠ Auto-upload not configured. Make sure {cloud_path} exists in bucket {config_obj.bucket_name}[/yellow]"
        )

    try:
        # Transcribe audio
        clean_text, srt_content, raw_json = transcribe_audio(config_obj, cloud_path)

        # Display result
        console.print("\n" + "=" * 50)
        console.print(
            Panel.fit(clean_text, title="[bold green]Transcription Result[/bold green]")
        )

        # Create outputs directory
        outputs_dir = Path("outputs")
        outputs_dir.mkdir(exist_ok=True)

        # Determine base filename
        if output_file:
            # Ensure output file is in outputs directory
            if not output_file.is_absolute() and output_file.parent.name != "outputs":
                output_file = outputs_dir / output_file.name
            base_name = output_file.stem
        else:
            base_name = input_file.stem if input_file else "transcription"

        # Save SRT file
        srt_file = outputs_dir / f"{base_name}.srt"
        with open(srt_file, "w", encoding="utf-8") as f:
            f.write(srt_content)
        console.print(f"[green]SRT file saved to:[/green] {srt_file}")

        # Save JSON if requested
        if save_json:
            json_file = outputs_dir / f"{base_name}.json"
            with open(json_file, "w", encoding="utf-8") as f:
                f.write(raw_json)
            console.print(f"[green]Raw JSON saved to:[/green] {json_file}")

    except Exception as e:
        console.print(f"[red]Transcription failed:[/red] {e}")
        console.print("\n[dim]Detailed error:[/dim]")
        console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command()
def status():
    """Show current configuration status"""
    config_obj = Config()

    console.print(
        Panel.fit("[bold blue]Configuration Status[/bold blue]", title="STT CLI Status")
    )

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Value", style="dim")

    table.add_row(
        "API Key",
        "✓ Configured" if config_obj.api_key else "✗ Missing",
        f"{config_obj.api_key[:10]}..." if config_obj.api_key else "Not set",
    )
    table.add_row(
        "Folder ID",
        "✓ Configured" if config_obj.folder_id else "✗ Missing",
        config_obj.folder_id or "Not set",
    )
    table.add_row(
        "Bucket Name",
        "✓ Configured" if config_obj.bucket_name else "✗ Missing",
        config_obj.bucket_name or "Not set",
    )

    console.print(table)

    if config_obj.is_configured():
        console.print("\n[green]✓ Configuration is complete![/green]")

        # Test API access
        console.print("\n[blue]Testing API access...[/blue]")
        try:
            headers = {
                "Authorization": f"Api-Key {config_obj.api_key}",
                "Content-Type": "application/json",
            }

            # Test with a simple request to check permissions
            test_url = "https://stt.api.cloud.yandex.net/stt/v3/recognizeStreaming"
            test_response = requests.post(
                test_url,
                headers=headers,
                json={"config": {"specification": {"audioEncoding": "OGG_OPUS"}}},
                verify=False,
            )

            if test_response.status_code == 403:
                console.print("[red]✗ API Access: Permission Denied[/red]")
                console.print(
                    "[yellow]Check that your service account has 'ai.speechkit-stt.user' role[/yellow]"
                )
            elif test_response.status_code == 401:
                console.print("[red]✗ API Access: Unauthorized[/red]")
                console.print(
                    "[yellow]Check your API key is correct and active[/yellow]"
                )
            else:
                console.print("[green]✓ API Access: OK[/green]")

        except Exception as e:
            console.print(f"[yellow]⚠ Could not test API access: {e}[/yellow]")
    else:
        console.print(
            "\n[red]✗ Configuration is incomplete. Run 'stt-cli config' to set up.[/red]"
        )


if __name__ == "__main__":
    app()

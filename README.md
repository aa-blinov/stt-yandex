# STT-CLI: Speech-to-Text CLI Tool

A comprehensive command-line tool that automatically converts audio to mono format and transcribes speech using Yandex Cloud Speech-to-Text API. Features speaker separation, timestamp extraction, and SRT subtitle generation.

## Features

- **Automatic audio conversion** to mono format (stored in `mono/` directory)
- **Speaker separation** with automatic detection (supports up to 2 speakers)
- **SRT subtitle generation** with precise timestamps and **duplicate removal**
- **Multi-format output**: Clean text, SRT subtitles, and raw JSON
- **Smart file organization** with `outputs/` directory
- **Interactive configuration** wizard
- **Progress tracking** with beautiful terminal interface
- **Non-interactive mode** - run commands without prompts when all parameters provided
- **File existence check** - prevents accidental overwriting of files in Object Storage
- **Normalized text preference** - automatically chooses properly formatted text with capitalization and punctuation

## Installation

```bash
uv sync
```

## Usage

### Configure credentials (first time setup)

```bash
uv run stt-cli config
```

### Transcribe audio

**Interactive mode (prompts for all parameters):**

```bash
uv run stt-cli transcribe
```

**Non-interactive mode (no prompts, runs automatically):**

```bash
uv run stt-cli transcribe input.ogg
```

**With custom output filename:**

```bash
uv run stt-cli transcribe input.ogg --output my_transcription
```

**Skip JSON output (SRT only):**

```bash
uv run stt-cli transcribe input.ogg --no-save-json
```

### Check configuration status

```bash
uv run stt-cli status
```

## Configuration

Create a `.env` file with your Yandex Cloud credentials:

```env
YANDEX_API_KEY=your_api_key_here
YANDEX_FOLDER_ID=your_folder_id_here
YANDEX_BUCKET_NAME=your_bucket_name_here
YANDEX_ACCESS_KEY_ID=your_access_key_id
YANDEX_SECRET_ACCESS_KEY=your_secret_access_key
```

## Output Files

The tool automatically organizes output files:

- **`mono/`** - Converted mono audio files (reused if already exists)
- **`outputs/`** - Transcription results:
  - `filename.srt` - SRT subtitle file with speaker labels and timestamps
  - `filename.json` - Raw API response (optional, enabled by default)

### SRT Format Example

The tool automatically separates up to 2 speakers and generates SRT subtitles:

```srt
1
00:00:24,439 --> 00:00:24,980
Спикер 1: Привет!

2
00:00:26,250 --> 00:00:27,740
Спикер 2: Да, ребята, всем привет привет.

3
00:00:32,399 --> 00:00:33,880
Спикер 1: Толик с Сашей как.
```

**Note:** Currently supports automatic detection of up to 2 speakers (Спикер 1, Спикер 2).

## Getting Yandex Cloud Credentials

### 1. API Key

1. Go to [Yandex Cloud Console](https://console.cloud.yandex.ru/) or [International Console](https://console.cloud.yandex.com/)
2. Navigate to **IAM** → **Service accounts**
3. Create a new service account or select existing one
4. Assign roles:
   - `ai.speechkit-stt.user` (required for speech recognition)
   - `storage.uploader` (only if you plan to upload files programmatically)
5. Create an **API key** for this service account
6. Copy the API key (format varies, but typically starts with letters and numbers)
7. **Important:** API key should be used with header `Authorization: Api-Key <your_api_key>` (this tool handles it automatically)

### 2. Folder ID

1. In Yandex Cloud Console, look at the URL
2. The folder ID is in the URL: `https://console.cloud.yandex.ru/folders/b1g2345abcde67890fgh`
3. Or go to **Resource Manager** → **Folders** and copy the ID
4. Format: `b1g2345abcde67890fgh`

### 3. Bucket Name

1. Go to **Object Storage** → **Buckets**
2. Create a new bucket or use existing one
3. Make sure the service account has access to this bucket
4. Use just the bucket name (without URLs)

**Note:** Object Storage credentials are optional - files can be uploaded manually via web interface.

## Workflow Example

1. **Setup credentials:**

   ```bash
   uv run stt-cli config
   ```

2. **Transcribe audio file:**

   ```bash
   uv run stt-cli transcribe my_audio.ogg
   ```

   The tool will:

   - Convert audio to mono (if needed) → `mono/my_audio_mono.ogg`
   - Upload to Yandex Cloud Storage (if configured)
   - Transcribe with speaker separation (up to 2 speakers)
   - Save results → `outputs/my_audio.srt` and `outputs/my_audio.json`

3. **Use the SRT file in video editors** like DaVinci Resolve, Premiere Pro, or any media player that supports subtitles.

## Troubleshooting

### Common Issues

**"Configuration is incomplete"**

- Run `uv run stt-cli status` to check what's missing
- Make sure all required parameters are configured

**"API Error [401]: Unauthorized"**

- Check your API key is correct and active
- Verify the service account has `ai.speechkit-stt.user` role
- Make sure the API key format is correct

**"Input file not found"**

- Check the local file path is correct
- File is used for mono conversion and upload

**"Audio conversion fails"**

- Install FFmpeg: `winget install FFmpeg` (Windows) or `brew install ffmpeg` (macOS)
- Check the audio file format is supported (OGG, MP3, WAV, etc.)

**"Error parsing response"**

- This usually indicates a temporary API issue
- Try running the command again
- Check the raw JSON output for detailed error information

**"Upload failed"**

- Verify Object Storage credentials are correct
- Check bucket permissions
- Ensure the bucket exists and is accessible

**"File already exists in Object Storage"**

- The script prevents overwriting existing files for safety
- Use a different filename with `--output` parameter
- Or manually delete the existing file from Object Storage first
- This check happens before audio conversion to save processing time

## File Organization

```text
project/
├── mono/                    # Converted mono audio files
│   └── filename_mono.ogg
├── outputs/                 # Transcription results
│   ├── filename.srt        # SRT subtitles with speakers
│   └── filename.json       # Raw API response
└── your_audio_files.ogg    # Original audio files
```

## Requirements

- Python 3.12+
- FFmpeg (for audio conversion)
- uv package manager

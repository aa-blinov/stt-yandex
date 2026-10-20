# stt-yandex

Transcribe Russian speech from an audio file with Yandex Cloud Speech-to-Text
and get an SRT subtitle file with the speakers labelled. The tool converts the
recording to mono, uploads it to a Yandex Object Storage bucket, waits for the
recognition to finish, and writes `outputs/<name>.srt` and
`outputs/<name>.json`; the plain transcript is printed to the terminal.

[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)

---

## Quick start

```bash
uv sync                  # install the tool and its dependencies
uv run stt-cli config    # write the Yandex Cloud credentials to .env
uv run stt-cli transcribe test.ogg
```

Python 3.12, `uv` and `ffmpeg` are what it needs. `ffmpeg` is what pydub calls
to decode the recording and to encode the mono copy, and without it the
conversion fails. The bucket has to exist before the run: the tool asks it
whether the object is already there, and stops if it is.

| Command | What it does |
| --- | --- |
| `uv run stt-cli config` | Asks for the credentials and writes them to `.env` in the current directory. |
| `uv run stt-cli transcribe FILE` | Converts, uploads, transcribes, writes the SRT and the JSON. |
| `uv run stt-cli status` | Prints which credentials are set and checks API access. |

`test.ogg` in the repository root is a 43:58 stereo recording of 30,526,435
bytes, and it is the one to point the command at.

## What it does

- **Mono conversion.** A recording with more than one channel is re-encoded to
  mono Ogg Opus at 64 kbit/s with `-application voip`, and written next to the
  source as `mono/<name>_mono.ogg`. If that file is already there, it is
  reused instead of being rebuilt.
- **Upload to Yandex Object Storage.** The mono file goes to the configured
  bucket over the S3-compatible API, with the object private. The upload can
  be skipped, and then the recording has to be put in the bucket by hand.
- **Recognition with speaker separation.** The `general` model, Russian only,
  with speaker labelling on, text normalisation on and the profanity filter
  off.
- **SRT subtitles with speaker labels.** One cue per segment, `HH:MM:SS,mmm`
  timings, and the speaker number in the cue text.
- **A plain transcript in the terminal.** The same segments, grouped by
  speaker, printed as a panel.
- **The raw API response.** The streaming JSON the service returned, written
  to `outputs/<name>.json` unless `--no-save-json` is passed.
- **Duplicate removal.** Segments with the same start, end and speaker are
  collapsed, keeping the one with the capitalisation and the punctuation.
- **Refusal to overwrite.** Before anything is uploaded the tool asks the
  bucket whether the object is already there, and stops if it is.

## How it works

```
file -> mono/ -> bucket -> recognizeFileAsync -> poll -> getRecognition -> outputs/
```

The whole tool is one module, `stt_cli.py`, with a `Config` class for the
credentials, functions for the conversion, the upload and the transcription,
and three Typer commands on top.

The recognition is asynchronous. `transcribe` posts to
`https://stt.api.cloud.yandex.net/stt/v3/recognizeFileAsync` with the model,
the container, the language whitelist, the text normalisation settings and the
speaker labelling, and gets an operation id back. It then polls
`https://operation.api.cloud.yandex.net/operations/<id>` every 10 seconds until
the operation is done, and fetches the transcript from
`https://stt.api.cloud.yandex.net/stt/v3/getRecognition`.

The answer comes back as newline-separated JSON, one object per line. Each line
is parsed on its own and a malformed line is skipped. The text is taken from
`finalRefinement.normalizedText.alternatives[0]` when the service sent a
refinement, and from `final.alternatives[0]` otherwise. The speaker number is
the channel tag plus one, which is what the speaker labelling produces.

The upload goes to Yandex Object Storage through the S3-compatible API, at the
endpoint `https://storage.yandexcloud.net`, in the region `ru-central1`, with
the object private. Without the static access keys the tool warns and carries
on, and the recording has to be in the bucket already, under the name the
tool expects.

## Configuration

The credentials live in a `.env` file in the directory the command is run
from. `stt-cli config` writes it and `stt-cli status` shows what it found.

| Variable | Needed for | What it does |
| --- | --- | --- |
| `YANDEX_API_KEY` | recognition | The Speech-to-Text API key, sent as `Authorization: Api-Key <key>`. |
| `YANDEX_FOLDER_ID` | recognition | The Yandex Cloud folder, sent as `x-folder-id`. |
| `YANDEX_BUCKET_NAME` | recognition and upload | The bucket the audio is uploaded to and read from. |
| `YANDEX_ACCESS_KEY_ID` | upload | The static access key id of the service account. |
| `YANDEX_SECRET_ACCESS_KEY` | upload | The static secret access key. |

Recognition needs the first three. The upload needs the last two and the
bucket name. A variable that is already set in the environment wins over the
one in the file, because `load_dotenv` does not overwrite.

The `config` command takes every value as an option, so it can run without a
prompt:
`uv run stt-cli config --api-key ... --folder-id ... --bucket-name ...`.
`--setup-upload` skips the question about the Object Storage keys.

| Option | Default | What it does |
| --- | --- | --- |
| `--output`, `-o` | the stem of the input file | The base name of the two files in `outputs/`. The directory is always `outputs/`. |
| `--save-json` / `--no-save-json` | `--save-json` | Whether the raw API response is written next to the SRT. |

The second positional argument of `transcribe` says where in the bucket the
object sits: `uv run stt-cli transcribe clip.ogg recordings/clip.ogg`. Without
it the object is named after the input file and sits in the root of the
bucket.

## Development

```bash
uv sync                # install, from uv.lock
uv run stt-cli --help  # the three commands
uv build               # the wheel, built by hatchling
```

There is no test suite and no CI in this repository. The tool has no build step
of its own: `uv sync` installs it into `.venv` and `stt-cli` runs from there,
so a change is checked by running the command against a bucket you control.
`uv build` produces `stt_yandex-0.1.0-py3-none-any.whl` and a source
distribution.

| Path | What it holds |
| --- | --- |
| `stt_cli.py` | The whole tool: `Config`, `convert_to_mono`, `upload_to_object_storage`, `check_file_exists_in_storage`, `transcribe_audio`, `generate_srt`, `ms_to_srt_time`, and the three commands. |
| `pyproject.toml` | The metadata, the six dependencies, and the `stt-cli = "stt_cli:app"` entry point. |
| `uv.lock` | The pinned dependency tree: 23 packages. |
| `test.ogg` | A 43:58 stereo Ogg Vorbis recording, 30,526,435 bytes. |
| `.python-version` | 3.12, the version `uv` builds the environment for. |

## License

MIT, © Alexander Blinov. See [LICENSE](LICENSE).

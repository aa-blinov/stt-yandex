# AGENTS.md — agent context for `stt-yandex`

A Python command line tool that transcribes Russian audio with Yandex Cloud
Speech-to-Text and writes an SRT file with the speakers labelled. Everything
lives in one module, `stt_cli.py`, and the only external service it talks to
is Yandex Cloud. This file is what you need to work on the project without
reading all of it.

## Run / build / test

```bash
uv sync                # install, from uv.lock
uv run stt-cli --help  # the three commands
uv run stt-cli status  # what is configured in the current directory
uv run stt-cli transcribe test.ogg
uv build               # the wheel and the source distribution
```

Python 3.12, `uv` and `ffmpeg` are required. There is no test suite and no CI
in this repository, so a change is checked by running the command against a
bucket you control.

## Where things live

| Path | What it holds |
| --- | --- |
| `stt_cli.py` | Everything: `Config`, `convert_to_mono`, `upload_to_object_storage`, `check_file_exists_in_storage`, `transcribe_audio`, `generate_srt`, `ms_to_srt_time`, and the three Typer commands. |
| `pyproject.toml` | The metadata, the six dependencies, the `stt-cli = "stt_cli:app"` entry point, and the hatchling wheel target. |
| `uv.lock` | The pinned dependency tree: 23 packages. |
| `test.ogg` | A 43:58 stereo Ogg Vorbis recording, 30,526,435 bytes. Usable as a conversion fixture. |
| `.python-version` | 3.12, the version `uv` builds the environment for. |
| `.gitignore` | A stock Python ignore list that also covers `.env`, `mono/` and `outputs/`. |

## Traps

- **The `.env` file is read from the working directory, not from the project
  root.** `ENV_FILE = Path(".env")` is relative, so `stt-cli status` in
  another directory reports an incomplete configuration even when `.env` sits
  next to the source. The same holds for `outputs/`: the results land in the
  directory the command was run from.
- **`mono/` follows the audio file and `outputs/` follows the working
  directory.** `convert_to_mono` writes to `input_path.parent / "mono"`, so
  `audio/clip.ogg` becomes `audio/mono/clip_mono.ogg`. The two directories are
  siblings only when the recording sits in the directory you run from.
- **The prompt for the path in the bucket is dead code.** In `transcribe` the
  question sits under `if input_file is None:`, but the loop above it
  guarantees `input_file` is a `Path` by then. The prompt never appears and
  the object key is always the input file's name. The second positional
  argument is the only way to set it.
- **A file that is already mono is uploaded unchanged, and the request still
  says `OGG_OPUS`.** `convert_to_mono` returns the input when
  `audio.channels == 1`, so a mono `.mp3` reaches the bucket as MP3 while the
  recognition request hardcodes `"containerAudioType": "OGG_OPUS"`. Convert
  the recording to Ogg yourself, or make the container part of the request.
- **An existing mono file is reused without looking at the source.** The
  function returns `output_path` as soon as it exists. Change the recording
  and the stale mono file is the one that gets uploaded, so delete
  `mono/<name>_mono.ogg` when the source changes.
- **`typer.Exit(1)` is caught by `except Exception` in the `transcribe`
  command.** The clean API error is printed, then "Transcription failed: 1"
  and a traceback follow, because `typer.Exit` inherits from `RuntimeError`.
  Raise it outside the try block, or catch `typer.Exit` before `Exception`.
- **`status` reports "API Access: OK" for a key that does not work.** The
  probe posts to `stt/v3/recognizeStreaming`, which is not an endpoint of the
  v3 API and answers 404, and only 401 and 403 are treated as failures.
  Everything else prints OK.
- **Every `requests` call to the Speech-to-Text API is made with
  `verify=False`,** and `urllib3.disable_warnings` hides the warning. The API
  key and the recording travel over a connection whose certificate is never
  checked. The boto3 upload to Object Storage is a separate path and keeps
  the default.
- **`--output` chooses the base name only.** The file is always written to
  `outputs/<name>.srt`, so an absolute `--output /tmp/x.srt` lands in
  `outputs/x.srt`.
- **`urllib3` is imported but never declared.** `stt_cli.py` imports it for
  `disable_warnings`, and it is absent from `pyproject.toml`. It works only
  because botocore pulls it in.
- **The polling loop has no timeout.** `while True` with `time.sleep(10)`
  between the polls of `operation.api.cloud.yandex.net`, so a stuck operation
  leaves the command running until it is interrupted.
- **The existence check runs before the conversion on purpose.** The object is
  checked against the bucket before the audio is touched, which saves the
  re-encode of a long recording when the run is going to be refused. The
  original README says as much. Keep that order.
- **`config` asks about Object Storage even when the keys were passed on the
  command line,** because the branch tests the saved configuration rather
  than the options in hand. `--setup-upload` skips the question.

## Style / safety rails

- **The speaker label is `Спикер N`.** It appears in every SRT the tool
  writes and in the transcript panel. The recognition is Russian, and the
  label follows it.
- **The language whitelist has one entry, `ru-RU`.** Adding a language is a
  product decision, not a refactor.
- **The tool's own output is in English.** Only the speaker label is Russian,
  and only because the recognition is.
- **Comments explain why, never what.** The comments in this codebase are
  good on this point. Keep them that way.
- **Do not add a dependency without a reason written down next to it.** Six
  are declared and `uv.lock` pins 23 packages.
- **The `.env` file never goes into the repository.** `.gitignore` covers it;
  keep it that way.

## Where the product truth lives

`PRODUCT.md` holds it. Read it before changing the behaviour of the tool, and
write the change there when the behaviour changes.

# Architecture

How stt-yandex is put together.

The tool is one module, `stt_cli.py`, 1,018 lines, with a `Config` class for
the credentials, eight functions for the work and three Typer commands on
top. There is no package directory, no console script beyond the one entry
point, and no test suite.

## The shape

The chain runs in one direction: a file goes in, and an SRT file, a JSON file
and a transcript come out. The recording is checked against the bucket
before it is touched, converted to mono, uploaded, transcribed by
Yandex Cloud, and written to disk.

| Name | What it is responsible for |
| --- | --- |
| `Config` | The five credentials, read from the environment and from `.env` in the working directory. It also writes the `.env` file back. |
| `convert_to_mono` | The conversion with pydub and ffmpeg, into `mono/<name>_mono.ogg` next to the recording. It returns the input untouched when the audio is already mono. |
| `upload_to_object_storage` | The upload through the S3-compatible API of Yandex Object Storage, with the object private. |
| `check_file_exists_in_storage` | The `head_object` call that decides whether the run is refused before the audio is read. |
| `pretty_api_error` | The translation of an API error body into a sentence for the terminal. |
| `transcribe_audio` | The whole recognition: the request, the polling, the parsing, the de-duplication, and the three values it returns. |
| `generate_srt` | The subtitle file, one cue per segment, with the speaker label in the cue text. |
| `ms_to_srt_time` | The timestamp format, `HH:MM:SS,mmm`. |
| `config` | The command that writes the `.env` file. Every value can be given as an option, so it can run without a prompt. |
| `transcribe` | The command that runs the chain and writes the outputs. |
| `status` | The command that prints the configuration and probes the API. |

## The data flow

```
file -> mono/ -> bucket -> recognizeFileAsync -> poll -> getRecognition -> outputs/
```

The recognition is asynchronous, so the chain has a wait in the middle.

```
input file
  |
  +-- check_file_exists_in_storage   the object key is checked against the
  |                                  bucket first, and a collision stops the
  |                                  run with exit code 1
  +-- convert_to_mono                pydub and ffmpeg, mono Ogg Opus at
  |                                  64 kbit/s with -application voip
  +-- upload_to_object_storage       skipped when the static keys are absent,
  |                                  in which case the recording has to be in
  |                                  the bucket already
  +-- transcribe_audio
  |     recognizeFileAsync           the model, the container, the language
  |                                  whitelist, the normalisation, the
  |                                  speaker labelling; an operation id
  |     poll                        every 10 seconds, no limit
  |     getRecognition              the transcript, as newline-separated JSON
  +-- generate_srt                  outputs/<name>.srt
  +-- write the raw response        outputs/<name>.json
```

Two directories are involved, and they do not sit in the same place. The
converted file goes to `mono/` next to the recording, and the results go to
`outputs/` in the directory the command was run from.

The answer comes back as newline-separated JSON, one object per line. Each
line is parsed on its own and a malformed line is skipped. The text is taken
from `finalRefinement.normalizedText.alternatives[0]` when the service sent
a refinement, and from `final.alternatives[0]` otherwise. The speaker number
is the channel tag plus one.

## Decisions worth knowing about

### The existence check comes before the conversion

The bucket is asked whether the object is already there before the audio is
touched. The check is cheap and the conversion of a long recording is not, so
a run that is going to be refused refuses itself before the work starts. The
cost is that the check needs the bucket name even when the upload itself is
skipped.

### The transcript is built from segments, and the segments are de-duplicated

Segments with the same start, the same end and the same speaker are
collapsed. Where two segments collide, the one that starts with a capital or
ends with a full stop wins, because the service sends both a raw and a
refined version of the same span.

### The SRT and the transcript are two renderings of one list

`transcribe_audio` returns the transcript, the SRT and the raw response
together. The transcript groups the segments by speaker and joins them with
a blank line; the SRT keeps one cue per segment with the timings. The
speaker label `Спикер N` is written into both.

### The upload is optional and the run continues without it

Without the static access keys the tool warns and carries on, and the
recording has to be in the bucket under the name the tool expects. The
object key takes the name of the input file unless the second positional
argument says otherwise.

### The polling loop has no timeout

`while True` with a ten second sleep between the polls, so a stuck operation
leaves the command running until it is interrupted.

## Boundaries

- **One module, no package.** `stt_cli.py` holds everything, and the entry
  point is `stt-cli = "stt_cli:app"`.
- **The commands do the talking, the functions do the work.** The three
  Typer commands print; the eight functions take arguments and return
  values. `pretty_api_error` is the one place that turns an API body into
  a sentence.
- **The credentials are read in one place.** `Config` is the only thing that
  touches the environment or the `.env` file, and every function that needs
  a credential takes a `Config`.
- **The API calls are made in two ways.** The Speech-to-Text calls go
  through `requests`, and the Object Storage calls go through boto3's S3
  client. They do not share a transport, and the certificate check is
  disabled on the first and left alone on the second.
- **No test suite and no CI.** A change is checked by running the command
  against a bucket you control.

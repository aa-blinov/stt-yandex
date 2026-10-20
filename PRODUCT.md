# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

The product is a terminal program: a Python 3.12 command line tool installed
with `uv`, with no server of its own and no platform-specific code. It runs on
macOS, Linux and Windows wherever Python 3.12, `uv` and `ffmpeg` are
available. The only region the code names is `ru-central1`, the Object
Storage region of Yandex Cloud.

## Users

The person who has a Russian-language recording and needs subtitles from it:
an interview, a lecture, a podcast episode, a recording of a call. The
situation the code answers is the one where the recording is already on a
disk, the person already has a Yandex Cloud account and a bucket, and the
last mile is the transcription and an SRT that a video editor or a player can
open.

Nothing in the repository narrows this further. The GitHub description is
empty, the repository has no stars, no forks and no download count, and the
only open pull request adopts the house standard. The audience beyond the
owner is not confirmed, and the record says so rather than guessing.

## Product Purpose

The tool turns one audio file into one SRT file with the speakers labelled.

The sequence is: convert to mono, upload the recording to a bucket, ask
Yandex Cloud Speech-to-Text to transcribe it, wait for the operation to
finish, write the subtitles and the raw response to disk. Everything the tool
does is in service of that one output.

Success for the user: `outputs/<name>.srt` opens in a video editor and the
cues carry the right times and the right speaker numbers. Success for the
product: the recording stays in the owner's own bucket, and the files land in
the directory the person ran the command from.

## Positioning

The tool is a wrapper around Yandex Cloud Speech-to-Text, and it should be
called one. What the service's own interface does not do is the chain around
the request: the mono conversion the recognition model requires, the upload,
the wait for the operation, the SRT with the speaker labels in it, and the
refusal to overwrite an object that is already in the bucket.

What a neighbour cannot copy from this code: nothing yet. The repository has
no published description, no download count, no comparison with another
transcription service and no measurement of any kind. A claim about a
difference in accuracy or speed between this tool and a neighbouring one would
need numbers that do not exist yet.

The open question is whether the tool stays a wrapper or grows a point of
view: a batch mode, a watch folder, subtitles shaped for one editor. Nothing
in the repository answers it.

## Operating Context

The person runs the tool in a directory that holds the audio, with a `.env`
beside them and a Yandex Cloud bucket they control. The recording is usually
longer than a minute and often around an hour: `test.ogg` in the repository is
43 minutes and 58 seconds, and the recognition is asynchronous, so the tool
polls the operation every 10 seconds and can sit there for a while.

The bucket has to exist before the run, because the object key is checked
against it before the audio is converted. The upload needs the static access
keys of a service account with the `storage.editor` role; without them the
tool still runs, but the recording has to be put in the bucket by hand under
the name the tool expects.

The output lands in `outputs/` in the directory the command was run from, and
the converted mono file lands in a `mono/` directory next to the recording.
The two are siblings only when the recording sits in the working directory.

`ffmpeg` has to be on the path. pydub calls it to decode the source and to
encode the mono copy.

## Capabilities and Constraints

Confirmed by the code:

- Three commands: `config`, `transcribe` and `status`.
- The audio is converted to mono with pydub and ffmpeg and re-encoded as Ogg
  Opus at 64 kbit/s with `-application voip`.
- The upload goes to Yandex Object Storage over the S3-compatible API, at
  `https://storage.yandexcloud.net`, in the region `ru-central1`, with the
  object private.
- The bucket is checked with `head_object` before anything is converted, and
  an object that is already there stops the run with exit code 1.
- The recognition request uses the `general` model, the `OGG_OPUS` container,
  a whitelist of one language, `ru-RU`, text normalisation on, the profanity
  filter off, `literatureText` on, and speaker labelling on.
- The request is asynchronous: `recognizeFileAsync` returns an operation id,
  the operation is polled every 10 seconds with no limit on the waiting, and
  the result comes from `getRecognition`.
- The answer is newline-separated JSON, each line parsed on its own, and a
  malformed line is skipped.
- The text comes from `finalRefinement.normalizedText` when the service sent
  it and from `final` otherwise; the speaker number is the channel tag plus
  one.
- Segments with the same start, end and speaker are collapsed, keeping the
  one that starts with a capital or ends with a full stop.
- The cue text is `Спикер N: <text>`, in Russian, in every subtitle file the
  tool writes.
- The outputs are `outputs/<name>.srt` and, unless `--no-save-json` is
  given, `outputs/<name>.json` with the raw response.
- The configuration is five values in a `.env` in the working directory.

Deliberately not true, and worth knowing before a change:

- There is no other language. The whitelist has one entry.
- There is no batch mode and no watch mode.
- There is no way to choose the output directory.
- There is no progress information about the recognition itself, only a
  spinner.
- The tool cleans nothing up: the uploaded object stays in the bucket and the
  mono file stays on disk.
- The polling loop has no timeout, so a stuck operation leaves the command
  running until it is interrupted.

Open, and not to be invented:

- The audience beyond the owner.
- Whether the speaker label follows the audio's language or stays in
  Russian. It is Russian because the recognition is Russian, and that is not
  the same as a decision.
- The licence of the code as it was before the house standard was adopted.
  The repository carried no `LICENSE` file and `pyproject.toml` declares no
  `license` field.

## Brand Commitments

**Name:** stt-yandex, with the command named `stt-cli`. **Tone:** technical
and quiet. The tool reports what it did, one line at a time, and stops with a
message when it cannot continue.

The interface is in English. The one exception is the speaker label in the SRT
and in the transcript panel, which is Russian, because the recognition is
Russian. The transcript is plain text grouped by speaker, so it can be copied
out of the terminal.

## Evidence on Hand

- `README.md` is the previous README. It describes the conversion, the upload,
  the speaker separation, the SRT and the troubleshooting cases, and it was
  written against the same code.
- `stt_cli.py` is the code: 1018 lines holding the recognition request, the
  parsing and the three commands.
- `pyproject.toml` and `uv.lock` hold the dependencies: six declared, 23
  packages resolved.
- `test.ogg` is a real recording: 43 minutes 58 seconds, Ogg Vorbis at
  96 kHz, stereo, 30,526,435 bytes.
- The behaviours recorded here that the code does not state were checked by
  running the tool: the `.env` lookup in the working directory, the mono
  directory next to the recording, the prompt for the bucket path that never
  appears, the traceback printed after an API error, and the `status` check
  that answers OK for a key that does not work.

Absent, and not to be invented: no stars, no forks, no download counts, no
testimonials, no comparison with another service, no second user, and no
repository description on GitHub. The repository has one commit and one open
pull request, which adopts the house standard.

## Product Principles

1. **The recording stays in the owner's bucket.** The tool sends the audio
   nowhere else and deletes nothing. The bucket belongs to the owner, and the
   tool is a guest in it.
2. **Nothing in the bucket is overwritten.** The check runs before the
   conversion, and a refusal is a refusal.
3. **The output is the SRT.** The subtitle file is the deliverable; the JSON
   is the evidence, and it can be turned off.
4. **Every step says what it did.** The tool prints the path it wrote, the
   object it uploaded and the operation it is waiting for, and stops with a
   message when it cannot go on.
5. **One dependency set, pinned.** `uv.lock` is the truth about what runs, and
   `pyproject.toml` says what the tool declares.

## Accessibility & Inclusion

- **The transcript is plain text.** It is printed grouped by speaker, so it
  can be read aloud, piped, or pasted into anything.
- **The state is stated in words.** `stt-cli status` prints a table with the
  state of every value, and the API key is shown truncated to ten characters.
- **Nothing rests on colour.** The tool uses the terminal's own palette, and
  every symbol it prints sits next to a word that carries the same meaning.
- **The language is fixed at Russian.** A recording in another language is
  outside the tool's scope. That is a product decision, and it has not been
  reviewed as one.
- **Nothing has been decided about screen readers or non-visual use.** The
  tool is a terminal program with spinners, and no accessibility work has been
  done on it.

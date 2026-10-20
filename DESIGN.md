---
name: stt-yandex
description: A terminal program that reports one fact per line, with the colour of the line stating what happened to that step.
colors:
  progress: "blue"
  done: "green"
  attention: "yellow"
  stopped: "red"
  label: "cyan"
  secondary: "dim"
  header: "bold magenta"
typography:
  body:
    fontFamily: "the terminal's monospace font"
    fontSize: "the terminal's own size"
    fontWeight: 400
    lineHeight: 1.0
  emphasis:
    fontFamily: "the terminal's monospace font"
    fontSize: "the terminal's own size"
    fontWeight: 700
    lineHeight: 1.0
rounded:
  none: "0"
spacing:
  line: "1"
  stage: "1"
---

# Design system: stt-yandex

## Overview

The interface of this tool is a terminal. There is no window, no stylesheet
and no font the program owns: the terminal's monospace face at the terminal's
own size, on the terminal's own palette.

What the program does own is the meaning that each colour carries. Rich's markup is the
only way a colour reaches the screen, and the tool uses eight of the eight
standard terminals do, one per outcome, and uses nothing else. A person
reading a log of a failed run can tell what happened from the colour of the
line alone, and then read the sentence to find out what.

The design is quiet on purpose. The tool transcribes a recording that is
often an hour long, and the person running it waits through a spinner and a
polling loop. Every line the tool prints is a fact, and nothing else is
printed.

**Key characteristics:**

- One fact per line: a label, a colon, the value.
- A colour states the outcome of a step, never the kind of a word.
- The only Russian in the output is the speaker label, `Спикер N`.
- Nothing is written in colour alone: every coloured line carries a word
  with the same meaning.

## Colors

The palette is the terminal's. The roles below name the standard terminal
colours, and the tool uses them for one purpose each.

### Primary

- **Progress** (`blue`): a step has begun. "Loading audio file:", "Uploading
  file to Object Storage:", "Starting transcription request...", "Retrieving
  transcription result...", "Testing API access...".
- **Done** (`green`): a step has finished. "✓ Mono audio saved:", "✓ File
  uploaded successfully!", "✓ Operation ID:", "✓ SRT file saved to:", "✓ Raw
  JSON saved to:", "✓ Configuration is complete!", "✓ API Access: OK".

### Secondary

- **Attention** (`yellow`): the run continues, and the person has to know
  something. "Converting 2-channel audio to mono...", "Bucket 'name' does
  not exist or is not accessible.", "Access denied. Check your credentials
  and bucket permissions.".
- **Stopped** (`red`): the run cannot continue. "Error during audio
  conversion:", "Upload failed [code]:", "File not found:", "Configuration is
  incomplete!", "✗ API Access: Permission Denied".

### Neutral

- **Label** (`cyan`): the name of a value. "Audio info:", "API Key:", "Folder
  ID:", "Bucket Name:". A cyan label never says whether the value is good.
- **Secondary** (`dim`): detail under the fact. "Compression ratio: 4.2x",
  "Press Enter to use 'name' in bucket root, or type custom path", "Detailed
  error:".
- **Header** (`bold magenta`): the header row of the configuration table, and
  nowhere else.

### Named rules

**The Colour States The Outcome Rule.** A colour appears on a line only
where it says what happened to a step: blue for a step that started, green
for one that finished, yellow for one that needs attention, red for one that
stopped the run.

**The Colour Never Carries The Meaning Alone Rule.** Every coloured line
carries a word with the same meaning. A green tick sits next to "saved", a
red cross sits next to "Permission Denied", and a reader who cannot see the
colour still knows what happened.

## Typography

There is no type scale, because there is no font the program sets. The
terminal chooses the face and the size, and rich prints into it. The only
typographic control the tool uses is `bold`, and it uses it for three things:
the command the person should run ("stt-cli config"), a panel body, and a
panel title.

Three rules govern the words:

- **One line, one fact.** A label, a colon, the value. The value follows the
  label on the same line.
- **Sentence case in English.** The output of the tool is in English,
  including the error messages.
- **One Russian label, and it is a product decision.** The speaker label
  `Спикер N` appears in every subtitle file the tool writes and in the
  transcript panel, because the recognition is Russian.

## Layout

The terminal is the container, and the line is the unit. A run reads top to
bottom, and each line belongs to one stage of the chain: convert, upload,
recognise, write. A blank line separates two stages.

The result is separated from the work by a rule of fifty `=` characters, and
the transcript itself sits in a panel fitted to the text. The configuration
view is a table with three columns: the parameter, its status centred, and
its value dimmed.

Nothing is boxed except the two panels. The transcript and the configuration
heading are the only framed things the tool prints.

## Components

### The status line

- **Shape:** a label in colour, a colon, then the value in the terminal's
  default ink.
- **Done:** the label is green and carries a tick, `✓`.
- **Stopped:** the label is red and carries a cross, `✗`.
- **Attention:** the label is yellow and carries a warning sign.

### The panel

- **Body:** the text, fitted, with a title on the border.
- **Titles:** "Transcription Result" in bold green, "STT CLI Status" in the
  terminal's default ink.
- **Body headings:** "Yandex Cloud STT Configuration" in bold blue,
  "Object Storage Configuration (Optional)" in bold yellow.

### The configuration table

- **Header:** bold magenta, with the words "Parameter", "Status" and
  "Value".
- **Columns:** the parameter in cyan, the status centred, the value dim.
- **Value:** the API key is shown truncated to ten characters and a
  trailing ellipsis, the folder id and the bucket name are shown whole.

### The spinner

- **Shape:** rich's `SpinnerColumn` and a text column, with no percentage
  and no bar.
- **Used for:** loading the audio, converting it and saving it. The
  conversion has no progress because pydub reports none.

### The prompt

- **Shape:** rich's `Prompt` and `Confirm`, one question at a time.
- **Labels:** cyan, and the value the person types is echoed back by the
  terminal.

## Do's and Don'ts

### Do:

- **Do** give every colour one job, and keep the job the same in every
  command.
- **Do** put the word next to the colour.
- **Do** print the path of every file the tool writes.
- **Do** keep the transcript plain text inside the panel, so it can be
  copied out of the terminal.

### Don't:

- **Don't** use a colour for decoration. The tool has no decoration.
- **Don't** print a fact without the label that names it.
- **Don't** change the meaning of a colour between commands. Blue is a step
  that started in `config` and in `transcribe`.
- **Don't** translate the speaker label. `Спикер N` is what a Russian
  subtitle file carries, and the tool writes Russian subtitles.

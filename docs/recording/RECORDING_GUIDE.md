<!-- AQIS lab WP-0.8 FR-0.8-02. Tests read the headings, tables and IDs of this guide
(tests/aqis_lab/test_aqis_recording_docs.py): keep them when editing. Sources: the Build Plan
(docs/specs/sources/AQIS_Test_Lab_Build_Plan.md, "Campaign A") and the owner's answers to BLK-014
(docs/approvals/WP-0.8.md). -->
# Recording guide: campaign A

## About campaign A
Campaign A records real speech for phase 1 of the AQIS Test Lab (Build Plan, "Campaign A"):
- 22 speakers, with mixed accents, genders and ages;
- 80 prompts per speaker, in about 30 minutes;
- recorded on the speakers' own phones;
- half the speakers in quiet rooms and half in everyday noise: 11 speakers in a quiet room and 11 speakers in an everyday noise room, each recording all 80 prompts (owner decision, BLK-014 A);
- about 1,760 turns in total.

Before a session starts:
1. The speaker reads and signs the consent form (`docs/recording/CONSENT_FORM.md`). The signed form is kept offline by the owner, never in the repository or in `AQIS_LAB`.
2. The session form (`docs/recording/SESSION_FORM.md`) is filled in.

## Speaker IDs and consent references
- Each speaker gets a pseudonymous speaker ID `ca-sNNN`: `ca-s001` to `ca-s022`, never a name.
- The consent reference is `ca-cNNN`, with the same number, for example `ca-c001` for `ca-s001`.
- The consent reference is written on the signed consent form and on the session form. It links the two without putting a name anywhere in the lab.

## The 80 prompts
The prompt families and their counts are the Build Plan's. The prompt texts themselves are written in phase 1.

| Family ID | Family | Prompts |
| --- | --- | --- |
| `f1` | Short answers | 15 |
| `f2` | Digit strings | 10 |
| `f3` | Names and places | 10 |
| `f4` | Questions | 10 |
| `f5` | Requests or complaints | 10 |
| `f6` | Emotional variants | 20 |
| `f7` | Thinking pauses | 5 |

Every speaker records all 80 prompts. Each prompt is recorded as its own recording, so that every file holds exactly one prompt.

## Phone
- Use the speaker's own phone and its built-in voice recorder.
- Hold the phone in the hand, 10-15 cm from the mouth, with no headset (owner decision, BLK-014 G). No earbuds or external microphone either.
- Keep the same hold and distance for the whole session.
- Write the phone's make and model on the session form.

## Rooms and background noise
Each speaker records the whole session in one room of one kind (owner decision, BLK-014 A and G):

| Room ID | Room |
| --- | --- |
| `room-quiet` | A quiet room |
| `room-everyday-noise` | An everyday noise room |

Write the main background noise on the session form, using one of these IDs (owner list, BLK-014 E):

| Noise ID | Noise source |
| --- | --- |
| `ns-fan` | Fan or air conditioner |
| `ns-traffic` | Traffic |
| `ns-tv` | Television |
| `ns-chatter` | People talking |
| `ns-kitchen` | Kitchen sounds |
| `ns-generator` | Generator |
| `ns-ambient` | General ambient noise |
| `ns-none` | No noticeable background noise |

## Accent groups
Write the speaker's accent group on the session form, using one of these IDs (owner list, BLK-014 F). For `acc-other`, describe the accent in the session form's notes.

| Accent ID | Accent group |
| --- | --- |
| `acc-south-asian-general` | South Asian English, general |
| `acc-urdu-influence` | English with Urdu influence |
| `acc-punjabi-influence` | English with Punjabi influence |
| `acc-pashto-influence` | English with Pashto influence |
| `acc-sindhi-influence` | English with Sindhi influence |
| `acc-neutral-urban` | Neutral urban English |
| `acc-other` | Other (described in the notes) |

## File naming
- Name every recording `<speaker-id>-<family-id>-<NN>.wav`, where `<NN>` is the prompt's number within its family, from 01. For example, `ca-s001-f2-07.wav` is speaker `ca-s001`, digit strings, prompt 7.
- The phone's original file keeps the same name with its own extension, for example `ca-s001-f2-07.m4a`.
- Names use only lowercase letters, digits and hyphens. The registry takes the file name without `.wav` as the clip ID, so every name is unique across all speakers: 22 × 80 = 1,760 names.

## Format
- The phone recorder's original file is kept as it is (owner decision, BLK-014 C).
- The lab converts a copy to the working format: 16 kHz, mono, 16-bit PCM WAV, with the same name and `.wav`.
- The registry imports only that format. The quality checks run on the converted WAV.

## Transfer
1. After the session, copy the recordings off the phone and name them by the file-naming rule.
2. Pack them, with the filled session form, into one archive per speaker session: `ca-sNNN.tar.gz`, for example `ca-s001.tar.gz` (owner decision, BLK-014 B).
3. Upload the archive to `MyDrive/AQIS_LAB/campaign_a/raw/`. Drive handles a few large archives far better than thousands of small files.
4. The signed consent form never goes into the archive or `AQIS_LAB`.

## Quality checks
Run these checks on every recording (owner thresholds, BLK-014 D).

| Check | How | Pass rule |
| --- | --- | --- |
| Complete set | Count the files against the 80 prompts | Exactly one file for each of the 80 prompts, named by the file-naming rule |
| Prompt match | Listen to the recording beside the prompt text | The speaker said the prompt word for word (verbatim) |
| Clipping | Count samples at full scale in the converted WAV | At most 0.1 % of samples at full scale |
| Level | Measure the peak level of the converted WAV | Peak at least -30 dBFS and at most -1 dBFS |
| Padding | Measure the silence before and after the speech | At least 0.3 s of silence at the start and at the end |

A recording that fails any check is recorded again by the same speaker, in the same room and with the same phone.

<!-- AQIS lab WP-0.8 FR-0.8-03. Tests read the field table of this form and its choice IDs
(tests/aqis_lab/test_aqis_recording_docs.py): keep them equal to docs/recording/RECORDING_GUIDE.md when editing.
The form holds no name or contact detail, so a filled copy can travel in the session archive. -->
# Session form: campaign A

Fill in one form per speaker session, before recording starts. Tick one choice where a list is given. The recording guide (`docs/recording/RECORDING_GUIDE.md`) explains every ID.

| Field | Entry | How to fill |
| --- | --- | --- |
| Speaker ID | ca-s___ | The speaker's pseudonymous ID, `ca-s001` to `ca-s022`; never a name. |
| Consent reference | ca-c___ | The number written on the speaker's signed consent form; the same number as the speaker ID. |
| Session date (UTC) | ____-__-__ | The recording date in UTC, written YYYY-MM-DD. |
| Device | ______________________ | The phone's make and model, held in the hand 10-15 cm from the mouth, with no headset. |
| Room | [ ] `room-quiet`  [ ] `room-everyday-noise` | The kind of room for the whole session. |
| Noise source | [ ] `ns-fan`  [ ] `ns-traffic`  [ ] `ns-tv`  [ ] `ns-chatter`  [ ] `ns-kitchen`  [ ] `ns-generator`  [ ] `ns-ambient`  [ ] `ns-none` | The main background noise during the session. |
| Accent group | [ ] `acc-south-asian-general`  [ ] `acc-urdu-influence`  [ ] `acc-punjabi-influence`  [ ] `acc-pashto-influence`  [ ] `acc-sindhi-influence`  [ ] `acc-neutral-urban`  [ ] `acc-other` | The speaker's accent group; for `acc-other`, describe the accent in the notes. |
| Notes | ______________________ | Anything that affected the recording, such as a prompt recorded again after a failed quality check. |

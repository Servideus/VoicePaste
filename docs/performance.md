# Longer recording: timing summary

A private 182-second Russian recording was tested three times per model. The recording and transcripts are excluded from this public repository.

| Model | Median successful response, seconds | Successes |
|---|---:|---:|
| 3.5 Transcribe verbatim | 5.178 | 3/3 |
| 2.5 Flash Lite | 5.596 | 3/3 |
| 3.5 Flash Lite | 6.316 | 3/3 |
| 2.5 Flash | 7.878 | 3/3 |
| 3.6 Flash | 8.576 | 3/3 |
| Flash Lite Latest | 10.065 | 3/3 |
| 3 Flash Preview | 15.251 | 3/3 |
| 3.5 Flash | 28.860 | 2/3 |

3.5 Flash returned 503 on its third attempt after 53.464 seconds. Medians exclude errors. The test timeout was 120 seconds; the application timeout is 30 seconds. Timings include client setup, connection, upload and the complete text response. Network/server load was not controlled; one recording does not establish general rankings. Four models were removed from the application by the user's decision after these results.

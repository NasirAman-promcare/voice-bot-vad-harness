# Sprint 1 scorecard

Config hash `a3ea46e38429`, data commit `5f3b76cf7a`, seed 20261019. Target WER is the mean over the caller slices of each slice's WER on its target conditions; the interval is a speaker-cluster bootstrap.

## Anchor check (brief section 8, item 2)

- canary-qwen-2.5b: measured 2.77 vs published 3.1 (-0.33 points): within ±0.7
- cohere-transcribe-2b: measured 2.15 vs published 2.37 (-0.22 points): within ±0.7
- parakeet-tdt-0.6b-v2: measured 3.06 vs published 3.19 (-0.13 points): within ±0.7, phone/clean 1.232

## Models

| model | role | target WER [95% CI] | clean WER | accent gap | phone cost | WebRTC cost | number acc. | medical recall | halluc. rate | RTFx | p50 ms | licence | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qwen3-asr-1.7b | heavy | 16.55% [15.23, 17.92] | 10.24% | 1.171 | 1.146 | 1.043 | 85.2% | 74.2% | 98.7% | 61.3 | 847 | Apache 2.0 | complete |
| parakeet-unified-0.6b | live | 18.06% [16.70, 19.51] | 11.81% | 1.271 | 1.124 | 1.022 | 84.5% | 68.7% | 0.0% | 352.6 | 180 | NVIDIA Open Model License | complete |
| parakeet-tdt-0.6b-v2 | live | 18.27% [16.94, 19.63] | 11.71% | 1.205 | 1.178 | 1.026 | 82.2% | 68.4% | 2.0% | 515.1 | 113 | CC BY 4.0 | complete |
| cohere-transcribe-2b | heavy | 18.30% [16.98, 19.74] | 12.57% | 1.172 | 1.096 | 1.001 | 84.4% | 71.9% | 11.3% | 216.7 | 228 | Apache 2.0 (gated) | complete |
| canary-qwen-2.5b | heavy | 18.59% [17.19, 20.14] | 10.89% | 1.190 | 1.277 | 1.048 | 84.7% | 72.2% | 34.7% | 42.8 | 1041 | CC BY 4.0 | complete |
| whisper-large-v3 | heavy | 19.15% [17.75, 20.61] | 12.14% | 1.163 | 1.191 | 1.033 | 86.5% | 73.9% | 91.7% | 52.6 | 507 | MIT | complete |
| whisper-large-v3-turbo | live | 22.07% [19.28, 25.96] | 12.74% | 1.261 | 1.324 | 1.005 | 86.2% | 71.6% | 79.3% | 86.1 | 150 | MIT | complete |
| granite-speech-4.1-2b | heavy | 22.52% [20.56, 24.41] | 12.78% | 1.173 | 1.411 | 1.054 | 85.8% | 70.5% | 89.3% | 45.1 | 754 | Apache 2.0 | complete |
| voxtral-realtime-4b | live | 30.42% [28.36, 32.74] | 20.59% | 1.496 | 1.315 | 1.047 | 78.2% | 56.8% | 0.0% | 1.0 | 5409 | Apache 2.0 | complete |

## Three worst cells per model (WER relative to the best model in the cell)

- **whisper-large-v3**: anchor/phone ×1.57; anchor/clean ×1.55; sa_conv/phone ×1.53
- **whisper-large-v3-turbo**: sa_conv/phone ×2.02; anchor/phone ×1.75; anchor/clean ×1.73
- **parakeet-tdt-0.6b-v2**: anchor/clean ×1.42; numbers/clean ×1.41; anchor/phone ×1.37
- **parakeet-unified-0.6b**: numbers/clean ×1.41; sa_conv/clean ×1.34; sa_conv/webrtc ×1.31
- **canary-qwen-2.5b**: medical/noise_0 ×1.54; sa_india/noise_0 ×1.43; us_conv/noise_0 ×1.40
- **granite-speech-4.1-2b**: us_conv/phone_noise_10 ×2.49; sa_conv/phone ×2.22; sa_conv/phone_noise_10 ×2.18
- **cohere-transcribe-2b**: sa_conv/clean ×1.44; us_conv/clean ×1.42; sa_conv/webrtc ×1.38
- **qwen3-asr-1.7b**: anchor/clean ×1.46; anchor/phone ×1.43; numbers/clean ×1.31
- **voxtral-realtime-4b**: medical/phone ×4.12; medical/webrtc_noise_10 ×3.98; medical/webrtc ×3.98

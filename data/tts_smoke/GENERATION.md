# Synthetic smoke clips (TTS)

These are synthetic speech, not human recordings. No person was recorded.

- Model: hexgrad/Kokoro-82M (Apache-2.0 weights), kokoro package 0.9.4
- Generated: 2026-09-27 in Google Colab, in a separate Python 3.12.3 environment made with uv (Kokoro does not support Colab's Python 3.13)
- Processing: 0.4 s of silence added at the start and the end; converted to 16 kHz mono 16-bit PCM WAV with ffmpeg

| File | Voice | Seconds | SHA-256 | Text |
| --- | --- | --- | --- | --- |
| 01.wav | af_heart | 4.15 | 46b1933eb76d9ebae401cdae6d0b713b2b2fb535e60c857265d0d5c67776937b | zero one two three four five six seven eight nine |
| 02.wav | am_michael | 5.00 | ea62b60e6330d174d2359e125ed28f771bd234ec98bd814cca6fbee99a636705 | what is the current temperature and weather outside right now |
| 03.wav | bf_emma | 4.42 | 6fb12c9cda37e061e33e43a4197d8561988347ffc051ce6954f7360d0ec99a77 | nine eight seven six five four three two one zero |
| 04.wav | bm_george | 4.97 | cd483c276dd2b92ee392481380cd66026067204682ad52049ffa0fc51a92b821 | please set an alarm for seven o'clock tomorrow morning |
| 05.wav | af_heart | 4.25 | 771a7be53f2042ee1aba0e3caf2015d8309a51843325b7120a3655232fe6ff9b | five four three two one zero nine eight seven six |
| 06.wav | am_michael | 4.72 | 13e43a63245a314220f09cf8408d5929a63451326ec30af6931f1230ae9063c3 | can you tell me how to get to the nearest train station from here |
| 07.wav | bf_emma | 4.55 | e0aaa3d5be86842c1c45abecf185343781938c49408005552c05cadc84ac1ef6 | two four six eight zero one three five seven nine |
| 08.wav | bm_george | 5.40 | 65e9a64fac659330c9e27b9ab740ae5c35372615f22c74679cdfb116f9506af8 | can you play the latest news and the market updates for today |
| 09.wav | af_heart | 4.20 | f64156ce89ad127dfb121bb8fa8a375dfb2d3094fb9f7ae5a523f34439ae5c3f | one three five seven nine zero two four six eight |
| 10.wav | bf_emma | 4.58 | bd627ded364b8b6ca678f8a62b152955df601c04f61ec1898877d189ec6052b5 | thank you very much for your help today and have a good evening |

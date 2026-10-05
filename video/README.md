# Demo video pipeline

Builds the 4:41 submission video: slides, three live demo runs of the web UI, a female English
narration (Kokoro TTS, voice `af_heart`) and burned-in captions.

1. `script.json`: narration text per segment (edit this to change what is said).
2. `tts.py`: synthesizes each sentence and writes `audio/*.wav` and `timeline.json` with timings.
   Needs `kokoro-onnx`, `soundfile`, and `kokoro-v1.0.onnx` and `voices-v1.0.bin` from
   https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0 in `voice/`.
3. `uvicorn inspectagent.api:app --port 8765`, then `record2.py`: records the demo runs with Playwright,
   timed to the narration.
4. `slides.py`: renders slides with headless Chromium.
5. `build.py`: cuts segments with ffmpeg, normalizes audio, writes `captions.srt`, `captions.ass` and the final MP4.

Run each step from one working folder. The scripts use the paths of the machine they were built on, so adjust them first.

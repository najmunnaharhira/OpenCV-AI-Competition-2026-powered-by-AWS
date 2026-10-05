import json, re, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
k = Kokoro("voice/kokoro-v1.0.onnx", "voice/voices-v1.0.bin")
SUBS = [(r"\bAWS\b", "A W S"), (r"\bS3\b", "S 3"), (r"\bSNS\b", "S N S"), (r"\bECC\b", "E C C"), (r"\bORB\b", "orb"),
        (r"RANSAC", "ran-sack"), (r"arm64", "arm 64"), (r"OpenCV", "Open C V"), (r"FastAPI", "Fast A P I"),
        (r"DynamoDB", "Dynamo D B"), (r"\bLLM\b", "L L M"), (r"\bURL\b", "U R L"), (r"X-Ray", "X ray"),
        (r"\bSAM\b", "Sam"), (r"InspectAgent", "Inspect Agent")]
def say(t):
    for a, b in SUBS: t = re.sub(a, b, t)
    s, sr = k.create(t, voice="af_heart", speed=1.0, lang="en-us")
    return s, sr
segs = json.load(open("script.json")); out = []
for seg in segs:
    chunks, cues, t = [], [], 0.4
    sr = 24000
    chunks.append(np.zeros(int(0.4 * sr), np.float32))
    for sent in seg["text"]:
        a, sr = say(sent)
        cues.append({"start": round(t, 3), "end": round(t + len(a) / sr, 3), "text": sent})
        chunks += [a.astype(np.float32), np.zeros(int(0.35 * sr), np.float32)]
        t += len(a) / sr + 0.35
    chunks.append(np.zeros(int(0.6 * sr), np.float32)); t += 0.6
    sf.write(f"audio/{seg['id']}.wav", np.concatenate(chunks), sr)
    out.append({**seg, "duration": round(t, 3), "cues": cues})
    print(seg["id"], round(t, 1))
json.dump(out, open("timeline.json", "w"), indent=1)
print("total", round(sum(s["duration"] for s in out), 1))

import json, subprocess
TL = json.load(open("timeline.json")); META = json.load(open("rec/meta.json"))
def run(a): subprocess.run(a, check=True)
parts, srt, t0, n = [], [], 0.0, 1
fmt = lambda t: f"{int(t//3600):02d}:{int(t%3600//60):02d}:{int(t%60):02d},{int(round((t%1)*1000)) % 1000:03d}"
for s in TL:
    D = s["duration"]; out = f"seg/{s['id']}.mp4"
    fade = f"fade=t=in:st=0:d=0.3,fade=t=out:st={D-0.3:.2f}:d=0.3"
    if s["kind"] == "slide":
        vin = ["-loop", "1", "-framerate", "30", "-t", f"{D}", "-i", f"slides/{s['id']}.png"]
        vf = f"scale=1920:1080,format=yuv420p,{fade}"
    else:
        m = META[s["id"]]
        vin = ["-ss", f"{m['start']}", "-i", f"rec/{s['id']}.webm"]
        vf = f"fps=30,scale=1920:1080:flags=lanczos,tpad=stop_mode=clone:stop_duration={D},trim=duration={D},format=yuv420p,{fade}"
    run(["ffmpeg", "-v", "error", "-y", *vin, "-i", f"audio/{s['id']}.wav", "-vf", vf, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
         "-t", f"{D}", out])
    parts.append(out)
    for c in s["cues"]:
        words, chunks, cur = c["text"].split(), [], ""
        for w in words:
            if len(cur) + len(w) + 1 > 95 and cur:
                chunks.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        chunks.append(cur)
        total = sum(len(x) for x in chunks); t = c["start"]
        for ch in chunks:
            d = (c["end"] - c["start"]) * len(ch) / total
            srt.append((t0 + t, t0 + t + d, ch)); t += d
    t0 += D
open("captions.srt", "w").write("\n".join(f"{i+1}\n{fmt(a)} --> {fmt(b)}\n{x}\n" for i, (a, b, x) in enumerate(srt)))
ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 0", "",
       "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
       "Style: Default,DejaVu Sans,40,&H00FFFFFF,&H00FFFFFF,&H60000000,&H60000000,0,0,0,0,100,100,0,0,3,12,0,2,160,160,70,1", "",
       "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
af = lambda t: f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"
ass += [f"Dialogue: 0,{af(a)},{af(b)},Default,,0,0,0,,{x}" for a, b, x in srt]
open("captions.ass", "w").write("\n".join(ass) + "\n")
open("seg/list.txt", "w").write("".join(f"file '{p.split('/')[1]}'\n" for p in parts))
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "seg/list.txt", "-c", "copy", "inspectagent_demo_nocaptions.mp4"])
_ = "FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H00FFFFFF,BackColour=&H99000000,BorderStyle=4,Outline=0,Shadow=0,MarginV=28,MarginL=120,MarginR=120"
run(["ffmpeg", "-v", "error", "-y", "-i", "inspectagent_demo_nocaptions.mp4", "-vf", "ass=captions.ass",
     "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "copy", "inspectagent_demo.mp4"])
print("total", round(t0, 1))

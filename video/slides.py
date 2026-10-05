import base64, subprocess
D = "/home/claude/opencv-ai-competition-2026-powered-by-aws/docs/diagrams/"
img = lambda f: "data:image/png;base64," + base64.b64encode(open(D + f, "rb").read()).decode()
CSS = """
*{box-sizing:border-box} body{margin:0;width:1920px;height:1080px;background:#fcfcfb;color:#1d1d1b;font-family:'DejaVu Sans',sans-serif;overflow:hidden}
.s{position:relative;width:1920px;height:1080px;padding:90px 120px}
h1{font-size:72px;margin:0 0 24px;letter-spacing:-1px} h2{font-size:56px;margin:0 0 40px}
p,li{font-size:34px;line-height:1.45;color:#3a3a37} .muted{color:#6b6b66} .acc{color:#2a78d6}
.foot{position:absolute;left:120px;right:120px;bottom:40px;font-size:22px;color:#8a8a84;display:flex;justify-content:space-between}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:36px;margin-top:30px}
.card{background:#fff;border:2px solid #e3e3de;border-radius:18px;padding:36px}
.card h3{font-size:36px;margin:0 0 16px} .card p{font-size:28px;margin:0}
.big{font-size:120px;font-weight:bold;line-height:1} .tag{display:inline-block;font-size:26px;padding:8px 18px;border:2px solid #d0d0ca;border-radius:30px;margin:6px 10px 0 0;color:#3a3a37}
table{border-collapse:collapse;font-size:30px} td,th{padding:14px 26px;border-bottom:2px solid #e3e3de;text-align:left} th{color:#6b6b66;font-weight:normal}
td.n{text-align:right;font-variant-numeric:tabular-nums} .win{font-weight:bold;color:#1d1d1b}
"""
FOOT = '<div class="foot"><span>InspectAgent · OpenCV 5 + AWS</span><span>OpenCV AI Competition 2026 · solo entry</span></div>'
def chart():
    data = [("No issue", 90, 100), ("Blur", 50, 97.5), ("Dark", 90, 100), ("Bright", 80, 97.5), ("Glare", 50, 100)]
    W, H, x0, y0, ph = 760, 520, 70, 30, 400
    gw = (W - x0) / len(data); bw = 46
    out = [f'<svg width="{W}" height="{H}" font-family="DejaVu Sans" font-size="20">']
    for v in (0, 50, 100):
        y = y0 + ph - ph * v / 100
        out.append(f'<line x1="{x0}" x2="{W}" y1="{y}" y2="{y}" stroke="#e3e3de" stroke-width="1.5"/><text x="{x0-12}" y="{y+7}" text-anchor="end" fill="#6b6b66">{v}%</text>')
    for i, (lab, b, a) in enumerate(data):
        cx = x0 + gw * i + gw / 2
        for j, (v, c) in enumerate(((b, "#eb6834"), (a, "#2a78d6"))):
            h = ph * v / 100; x = cx - bw - 1 + j * (bw + 2)
            out.append(f'<path d="M{x},{y0+ph} v{-(h-4)} q0,-4 4,-4 h{bw-8} q4,0 4,4 v{h-4} z" fill="{c}"/>')
            out.append(f'<text x="{x+bw/2}" y="{y0+ph-h-10}" text-anchor="middle" fill="#3a3a37" font-size="18">{v:g}</text>')
        out.append(f'<text x="{cx}" y="{y0+ph+34}" text-anchor="middle" fill="#3a3a37">{lab}</text>')
    out.append("</svg>")
    return "".join(out)
S = {
"s01_title": f'''<div class="s" style="padding-top:250px"><div class="muted" style="font-size:30px">OpenCV AI Competition 2026, powered by AWS</div>
<h1 style="font-size:110px;margin-top:20px">InspectAgent</h1><p style="font-size:44px">Agentic visual inspection with <span class="acc">OpenCV 5</span> and <span class="acc">AWS</span></p>
<p class="muted" style="margin-top:60px;font-size:32px">Solo entry by najmunnahar · Agentic Vision path</p></div>''',
"s02_problem": f'''<div class="s"><h2>One photo, one chance</h2><p>One-shot inspection runs a fixed pipeline on a single image.<br>When the <b>image</b> is bad, the <b>decision</b> is bad.</p>
<div class="cards"><div class="card"><div class="big" style="color:#eb6834">50%</div><p>accuracy of a one-shot OpenCV pipeline on <b>blurry</b> images</p></div>
<div class="card"><div class="big" style="color:#eb6834">50%</div><p>accuracy on images with <b>glare</b></p></div>
<div class="card"><div class="big" style="color:#eb6834">40%</div><p>of good parts wrongly <b>rejected</b> overall</p></div></div>{FOOT}</div>''',
"s03_idea": f'''<div class="s"><h2>Inspect like a person would</h2><div class="cards" style="margin-top:60px">
<div class="card"><h3>1 · Look again</h3><p>Bad focus, exposure or glare? Change the camera setting and recapture.</p></div>
<div class="card"><h3>2 · Lean in</h3><p>Evidence close to the threshold? Take a close-up at higher sensitivity.</p></div>
<div class="card"><h3>3 · Ask first</h3><p>Critical defect? Request human approval before quarantining the lot.</p></div></div>{FOOT}</div>''',
"s04_arch": f'''<div class="s" style="padding:50px 120px"><img src="{img('architecture.png')}" style="width:1680px;display:block;margin:0 auto">{FOOT}</div>''',
"s05_workflow": f'''<div class="s" style="padding:30px 160px"><img src="{img('agent_workflow.png')}" style="width:1600px;display:block;margin:0 auto">{FOOT}</div>''',
"s09_results": f'''<div class="s"><h2>Results: 200 parts, agent vs. one-shot</h2><div style="display:flex;gap:70px;align-items:flex-start">
<table><tr><th></th><th>one-shot</th><th>InspectAgent</th></tr>
<tr><td>Pass/fail accuracy</td><td class="n">72.0%</td><td class="n win">99.0%</td></tr>
<tr><td>Defects passed</td><td class="n">16.0%</td><td class="n win">2.0%</td></tr>
<tr><td>Good parts rejected</td><td class="n">40.0%</td><td class="n win">0.0%</td></tr>
<tr><td>Matches policy</td><td class="n">60.5%</td><td class="n win">97.0%</td></tr>
<tr><td>Captures per part</td><td class="n">1.0</td><td class="n">1.8</td></tr></table>
<div><div style="font-size:26px;color:#3a3a37;margin-bottom:6px">Accuracy by capture problem</div>
<div style="font-size:22px;color:#3a3a37;margin-bottom:8px"><span style="display:inline-block;width:18px;height:18px;background:#eb6834;border-radius:4px;vertical-align:-2px"></span> one-shot &nbsp;&nbsp;
<span style="display:inline-block;width:18px;height:18px;background:#2a78d6;border-radius:4px;vertical-align:-2px"></span> InspectAgent</div>{chart()}</div></div>
<p class="muted" style="font-size:24px;margin-top:10px">Synthetic inspection cell, seed 11. Reproduce: python -m eval.run_eval --n 200 --seed 11</p>{FOOT}</div>''',
"s10_safety": f'''<div class="s"><h2>Failure handling and human control</h2><div class="cards">
<div class="card"><h3>Guardrails</h3><p>Executor refuses a pass without a real check, and an auto-reject of a critical defect.</p></div>
<div class="card"><h3>Fallback</h3><p>Bedrock error or refusal → rule planner continues, event logged.</p></div>
<div class="card"><h3>Observability</h3><p>One JSON log line per step with OpenCV measurements. Traces and evidence in S3.</p></div></div>
<div class="card" style="margin-top:36px;font-family:'DejaVu Sans Mono',monospace;font-size:24px;line-height:1.6;color:#3a3a37">
4 reject_part {{"rationale": "just scrap it"}}<br><span style="color:#b3261e">→ guardrail: critical defect; request_human_approval(quarantine_lot) is required</span><br>
5 request_human_approval {{"proposed_action": "quarantine_lot"}} → pending</div>{FOOT}</div>''',
"s11_limits": f'''<div class="s"><h2>Limitations and next steps</h2><ul style="margin-top:20px">
<li>Results come from a reproducible <b>synthetic</b> inspection cell. Real-image evaluation is next.</li>
<li><b>2 of 100</b> defective parts missed (faint spots). <b>4</b> stains labelled as minor spots.</li>
<li>Golden-reference method needs one reference image per part type.</li>
<li>Next: real camera driver, more part types, COOL on Graviton benchmark.</li></ul>{FOOT}</div>''',
"s12_close": f'''<div class="s" style="padding-top:260px;text-align:center"><h1 style="font-size:96px">Thank you</h1>
<p style="font-size:38px">Code, technical report and evaluation</p><p class="acc" style="font-size:34px">github.com/najmunnaharhira/OpenCV-AI-Competition-2026-powered-by-AWS</p>
<p class="muted" style="font-size:30px;margin-top:50px">InspectAgent · solo entry by najmunnahar</p></div>''',
}
B = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
for k, body in S.items():
    open(f"slides/{k}.html", "w").write(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>")
    subprocess.run([B, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--window-size=1920,1280",
                    f"--screenshot=/tmp/claude-0/video/slides/{k}_raw.png", f"file:///tmp/claude-0/video/slides/{k}.html"], capture_output=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"slides/{k}_raw.png", "-vf", "crop=1920:1080:0:0", f"slides/{k}.png"])
    print(k)

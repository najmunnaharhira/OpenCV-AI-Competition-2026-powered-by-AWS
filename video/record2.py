import asyncio, json, shutil, time
from playwright.async_api import async_playwright
TL = {s["id"]: s for s in json.load(open("timeline.json"))}
CSS = ("body{font-size:17px} main{max-width:1560px} code{font-size:13px} "
       ".grid{grid-template-columns:0.9fr 1.5fr 1.3fr} #ev{display:grid;grid-template-columns:1fr 1fr;gap:8px} #ev img{margin:0}")
async def main():
    meta = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        for sid in ["s06_demo_blur", "s07_demo_faint", "s08_demo_critical"]:
            s = TL[sid]; D = s["duration"]
            pre, post = 1.6, 3.5 if s.get("approve") else 2.5
            step_ms = int((D - pre - post - 0.5) / s["steps"] * 1000)
            ctx = await b.new_context(viewport={"width": 1600, "height": 900}, color_scheme="light",
                                      record_video_dir="rec/tmp", record_video_size={"width": 1600, "height": 900})
            t0 = time.time()
            pg = await ctx.new_page()
            await pg.goto(f"http://127.0.0.1:8765/?step_ms={step_ms}")
            await pg.add_style_tag(content=CSS)
            await pg.wait_for_selector("#part option", state="attached")
            await pg.select_option("#part", s["part"])
            start = time.time() - t0
            await pg.wait_for_timeout(int(pre * 1000))
            await pg.click("#go")
            await pg.wait_for_function("document.querySelector('#outcome b.big') !== null", timeout=120000)
            if s.get("approve"):
                await pg.wait_for_timeout(1200)
                await pg.click("#approve-yes")
            remaining = D - (time.time() - t0 - start)
            await pg.wait_for_timeout(int(max(remaining, 0.5) * 1000) + 500)
            path = await pg.video.path()
            await ctx.close()
            shutil.move(path, f"rec/{sid}.webm")
            meta[sid] = {"start": round(start, 2), "duration": D, "step_ms": step_ms}
            print(sid, meta[sid])
        await b.close()
    json.dump(meta, open("rec/meta.json", "w"))
asyncio.run(main())

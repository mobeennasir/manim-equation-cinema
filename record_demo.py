"""Record a real portrait screen demo of the Manim Equation Cinema website.

Steps: open home -> pick the Rainbow Roses preset -> click Render ->
wait for the result page -> let the video play -> scroll to the audio
suggestion -> back home to the Your videos list.
Logs epoch timestamps for the render click and the result arrival, so
the long render wait can be jump-cut in post-production.
"""
import json
import time

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:5000"
OUT_DIR = "/tmp/demo-recording"
LOG = "/tmp/demo-recording/times.json"

times = {"start": time.time()}

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/home/hatch/workspace/tools/chrome-linux64/chrome",
        args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"],
    )
    ctx = browser.new_context(
        viewport={"width": 720, "height": 1280},
        record_video_dir=OUT_DIR,
        record_video_size={"width": 720, "height": 1280},
    )
    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_timeout(3000)  # let the viewer read the home page

    # Pick the preset (Rainbow Roses) and show the choice.
    page.select_option('select[name="preset"]', "rainbow-roses")
    page.wait_for_timeout(2500)

    # Also show a custom equation being typed, so both ways are visible:
    # switch back to Custom, type a sine wave, then back to the preset.
    page.select_option('select[name="preset"]', "")
    page.fill('input[name="expr1"]', "sin(x)")
    page.wait_for_timeout(1500)
    page.select_option('select[name="preset"]', "rainbow-roses")
    page.wait_for_timeout(1500)

    # Quality: low = fastest render for the demo.
    page.select_option('select[name="quality"]', "low")
    times["click_render"] = time.time()
    page.click('button[type="submit"]', no_wait_after=True)
    # The server renders now (v5 auto loops: about a minute for roses).
    # The form POST holds the response until the render finishes, so
    # the click must NOT wait for the navigation — the wait below does.
    page.wait_for_selector("video", timeout=600_000)
    times["result"] = time.time()
    page.wait_for_timeout(7000)  # let the video play in the player
    # Scroll down to the audio suggestion box and the Download button.
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(3500)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(2000)
    # Back home: the Your videos list now shows the new render.
    page.goto(URL)
    page.wait_for_timeout(3500)
    times["end"] = time.time()
    ctx.close()
    browser.close()

with open(LOG, "w") as fh:
    json.dump(times, fh, indent=2)
print(json.dumps(times, indent=2))
print("Render wait was %.0fs" % (times["result"] - times["click_render"]))

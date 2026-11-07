"""
app.py — local web server: type an equation in your browser, get a video.

Run:   python app.py
Open:  http://127.0.0.1:5000

How it works — the exact flow you asked for:
1. You open http://127.0.0.1:5000 in your browser (localhost, your own computer).
2. You type an equation and click Render. The server runs Manim.
3. You do NOT get a bare file straight away. You land on a result page
   with the finished video playing right there in the browser
   (an embedded <video> player — play, pause, scrub, fullscreen).
4. Under the player is a Download button. Clicking it saves the .mp4
   to your device (Downloads folder). The same file is also in outputs/.
Nothing is uploaded anywhere — it all runs on your own computer.

Deploy note: this same file is what Koyeb runs (see Dockerfile).
On a free host, rendering is slow and can time out — test locally first.
"""

import os
import shutil
import subprocess
import sys
import time
import uuid

from flask import Flask, redirect, render_template_string, request, send_file, url_for

from audio import audio_for, fmt_time
from equations import PRESETS, config_from_preset, latex_of, save_config, validate_config

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "outputs")
JOBS_DIR = os.path.join(BASE, "jobs")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(JOBS_DIR, exist_ok=True)

app = Flask(__name__)

PAGE = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Manim Equation Cinema</title>
<meta name="description" content="Type any equation and Manim draws it cinematically as a video you can download.">
<link href="https://fonts.googleapis.com/css2?family=Mona+Sans:wdth,wght@100,400;100,500;125,300&display=swap" rel="stylesheet">
<style>
/* Hallmark · shape: app screen · genre: atmospheric · theme: Midnight (deal 1/3, seed equation-cinematic-video-generator-13d1·f51d8f6a·2026-11-07·r0)
 * nav: none · signature: the render form · states: default, hover, focus-visible, active, disabled
 * axes: dark/grotesk-sans/cool · posture: committed · contrast: pass · v2.0.0 */
/* Hallmark · pre-emit critique: P_ H_ E_ S_ R_ V_ · weakest: _, <what you did about it> */
:root {
  color-scheme: dark;
  --space-3xs: 2px; --space-2xs: 4px; --space-xs: 8px; --space-sm: 12px; --space-md: 16px; --space-lg: 24px; --space-xl: 40px; --space-2xl: 64px; --space-3xl: 96px; --space-4xl: 144px;
  --text-xs: 0.75rem; --text-sm: 0.875rem; --text-md: 1rem; --text-lg: 1.2rem; --text-xl: 1.44rem; --text-2xl: 1.728rem; --text-3xl: 2.074rem;
  --text-display-s: 1.44rem; --text-display: 1.728rem; --text-section: 1.2rem; --text-title: 1rem; --text-lead: 1rem;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1); --ease-in: cubic-bezier(0.7, 0, 0.84, 0); --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-micro: 120ms; --dur-short: 220ms; --dur-long: 420ms;
  --color-error: oklch(72% 0.15 27); --color-success: oklch(76% 0.13 150);
  --color-paper: oklch(14% 0.048 264); --color-paper-2: oklch(18.5% 0.052 264); --color-paper-3: oklch(23% 0.055 264);
  --color-ink: oklch(95% 0.016 250); --color-ink-2: oklch(88% 0.05 245); --color-muted: oklch(73% 0.04 256);
  --color-rule: oklch(29% 0.058 264); --color-rule-2: oklch(40% 0.06 262);
  --color-accent: oklch(80% 0.11 230); --color-accent-2: oklch(58% 0.1 236); --color-accent-ink: oklch(16% 0.05 264); --color-focus: oklch(84% 0.12 228);
  --font-display: "Mona Sans", ui-sans-serif, system-ui, sans-serif; --font-body: var(--font-display); --font-outlier: var(--font-display);
  --radius-card: 0; --radius-pill: 0; --rule-hair: 1px;
  --shadow-card: 0 24px 48px -24px oklch(6% 0.04 264 / 0.7);
  --tracking-display: -0.015em; --display-weight: 300; --display-stretch: 125%;
}
*, *::before, *::after { box-sizing: border-box; }
html, body { overflow-x: clip; }
html { scrollbar-color: var(--color-muted) var(--color-paper); }
body { margin: 0; background: var(--color-paper); color: var(--color-ink); font-family: var(--font-body); font-size: var(--text-md); line-height: 1.55; -webkit-font-smoothing: antialiased; caret-color: var(--color-accent); }
::selection { background: color-mix(in oklab, var(--color-accent) 22%, transparent); color: var(--color-ink); }
:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
a { color: inherit; text-decoration-thickness: 1px; text-underline-offset: 0.16em; }
a:hover { text-decoration-color: var(--color-accent); }
h1, h2, h3 { margin: 0; font-family: var(--font-display); font-weight: var(--display-weight); font-stretch: var(--display-stretch); font-synthesis: none; letter-spacing: var(--tracking-display); line-height: 1.04; overflow-wrap: break-word; min-width: 0; text-wrap: balance; }
h1 { max-width: 20ch; font-size: var(--text-display); }
h2 { max-width: 30ch; font-size: var(--text-section); }
h3 { max-width: 40ch; font-size: var(--text-title); line-height: 1.2; font-weight: 500; }
.lead { font-size: var(--text-lead); line-height: 1.45; max-width: 52ch; color: var(--color-ink-2); }
p { margin: 0; text-wrap: pretty; }
p:not([class]) { max-width: 65ch; }
img, video { max-width: 100%; height: auto; display: block; }
svg { display: block; }
button, input, select, textarea { font: inherit; }
.shell { width: 100%; max-width: 960px; margin-inline: auto; padding-inline: var(--space-lg); padding-block: var(--space-xl) var(--space-2xl); }
.masthead { margin-bottom: var(--space-xl); }
.wordmark { display: flex; align-items: center; gap: var(--space-sm); }
.wordmark svg { width: 28px; height: 28px; flex: none; color: var(--color-accent); }
.wordmark h1 { font-size: var(--text-display); }
.masthead .lead { margin-top: var(--space-md); }
.settle { animation: settle var(--dur-long) var(--ease-out) both; }
@keyframes settle { from { opacity: 0.6; } }
.err { background: var(--color-paper-3); border-left: 2px solid var(--color-error); color: var(--color-ink); padding: var(--space-md); margin-bottom: var(--space-lg); }
.well { background: var(--color-paper-2); padding: var(--space-lg); margin-bottom: var(--space-lg); }
.well h2 { margin-bottom: var(--space-md); }
.field { margin-bottom: var(--space-md); }
.field:last-child { margin-bottom: 0; }
label { display: block; font-size: var(--text-sm); font-weight: 500; color: var(--color-muted); margin-bottom: var(--space-xs); }
input, select { width: 100%; padding: var(--space-sm); background: var(--color-paper); border: var(--rule-hair) solid var(--color-muted); border-radius: var(--radius-card); color: var(--color-ink); font-size: var(--text-md); }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-md); }
.hint { font-size: var(--text-sm); color: var(--color-muted); margin-top: var(--space-xs); }
.btn { display: inline-flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-lg); font-weight: 500; font-size: var(--text-md); border: var(--rule-hair) solid transparent; background: none; border-radius: var(--radius-pill); color: var(--color-ink); cursor: pointer; white-space: nowrap; transition: background-color var(--dur-short) var(--ease-out); }
.btn svg { width: 16px; height: 16px; flex: none; }
.btn--primary { background: var(--color-accent); color: var(--color-accent-ink); }
.btn--primary:hover { background: var(--color-accent-2); color: var(--color-accent-ink); }
.btn--secondary { border-color: var(--color-rule-2); }
.btn--secondary:hover { background: var(--color-paper-2); }
.btn:active { transform: translateY(1px); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
section { margin-bottom: var(--space-xl); }
section > .lead { margin-top: var(--space-xs); margin-bottom: var(--space-md); }
.rows { list-style: none; margin: 0; padding: 0; }
.rows li { display: flex; justify-content: space-between; align-items: baseline; gap: var(--space-md); padding-top: var(--space-sm); padding-bottom: var(--space-sm); border-top: var(--rule-hair) solid var(--color-rule); }
.rows li:last-child { border-bottom: var(--rule-hair) solid var(--color-rule); }
.row-title { font-weight: 500; flex: none; }
.rows .row-text { color: var(--color-ink-2); text-align: right; }
.rows code { font-variant-numeric: tabular-nums; }
.note { font-size: var(--text-sm); color: var(--color-muted); line-height: 1.6; margin-bottom: var(--space-xl); }
.actions { display: flex; gap: var(--space-md); flex-wrap: wrap; align-items: center; }
@media (max-width: 40rem) {
  .shell { padding-inline: var(--space-md); }
  .row { grid-template-columns: 1fr; }
  .rows li { flex-direction: column; gap: var(--space-2xs); align-items: flex-start; }
  .rows .row-text { text-align: left; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; } }
</style></head><body>
<div class="shell">
<header class="masthead settle">
  <div class="wordmark">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="0"/><path d="M3 9h18M7 5l2.5 4M12 5l2.5 4M17 5l2.5 4"/></svg>
    <h1>Manim Equation Cinema</h1>
  </div>
  <p class="lead">Type any equation. Manim draws it cinematically and you download the video.</p>
</header>
{% if error %}<div class="err" role="alert">{{ error }}</div>{% endif %}
<form method="post" action="/render">
  <section class="well" aria-label="Equation">
    <h2>Equation</h2>
    <div class="field">
      <label for="preset">Preset</label>
      <select id="preset" name="preset"><option value="">Custom: use the fields below</option>
      {% for k,v in presets.items() %}<option value="{{ k }}">{{ v.label }} (viral {{ v.viral }}/5)</option>{% endfor %}</select>
    </div>
    <div class="field">
      <label for="mode">Mode</label>
      <select id="mode" name="mode"><option value="y">y = f(x)</option><option value="parametric">Parametric x(t), y(t)</option><option value="polar">Polar r(θ)</option></select>
    </div>
    <div class="row">
      <div class="field"><label for="expr1">y = / r = / x(t) =</label><input id="expr1" name="expr1" value="sin(x)" placeholder="sin(x)"></div>
      <div class="field"><label for="expr2">y(t) =</label><input id="expr2" name="expr2" value="sin(t)" placeholder="sin(t)"><p class="hint">Parametric only.</p></div>
    </div>
    <div class="row">
      <div class="field"><label for="rmin">Range from</label><input id="rmin" name="rmin" value="-6.28"></div>
      <div class="field"><label for="rmax">Range to</label><input id="rmax" name="rmax" value="6.28"></div>
    </div>
  </section>
  <section class="well" aria-label="Render settings">
    <h2>Render</h2>
    <div class="row">
      <div class="field"><label for="duration">Draw time (seconds)</label><input id="duration" name="duration" value="8"><p class="hint">How long the drawing takes.</p></div>
      <div class="field"><label for="color">Colour</label><input id="color" name="color" value="#22d3ee"></div>
    </div>
    <div class="row">
      <div class="field"><label for="quality">Quality</label><select id="quality" name="quality"><option value="medium">720p (recommended)</option><option value="low">480p (fast test)</option><option value="high">1080p (slow)</option></select></div>
      <div class="field"><label for="camera">Camera movement</label><select id="camera" name="camera"><option value="on">On: slow zoom (cinematic)</option><option value="off">Off: fixed camera</option></select></div>
    </div>
  </section>
  <div class="actions">
    <button class="btn btn--primary" type="submit"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>Render video</button>
  </div>
  <p class="hint">Takes 30 seconds to a few minutes.</p>
</form>
<section aria-label="Examples to try">
  <h2>Examples to try</h2>
  <ul class="rows">
    <li><span class="row-title">y = sin(x)</span></li>
    <li><span class="row-title">y = x^2 / 4</span></li>
    <li><span class="row-title">Parametric</span><span class="row-text"><code>cos(t), sin(t)</code></span></li>
    <li><span class="row-title">Polar</span><span class="row-text"><code>2*sin(3*theta)</code></span></li>
    <li><span class="row-title">Preset</span><span class="row-text">Butterfly</span></li>
  </ul>
</section>
<p class="note">Videos are saved in the outputs/ folder too. The video itself is silent. After rendering you get a song suggestion (name and timestamps) to add in Instagram or CapCut.</p>
<section aria-label="Most viral presets">
  <h2>Most viral presets</h2>
  <p class="lead">Try these first.</p>
  <ul class="rows">{% for k,v in presets.items() %}{% if v.viral >= 5 %}<li><span class="row-title">{{ v.label }}</span><span class="row-text">{{ v.story or v.why }}</span></li>{% endif %}{% endfor %}</ul>
</section>
{% if videos %}<section aria-label="Your videos">
  <h2>Your videos</h2>
  <p class="lead">Select one to preview.</p>
  <ul class="rows">{% for v in videos %}<li><span class="row-title">{{ v }}.mp4</span><span class="row-text"><a href="/result/{{ v }}">Preview</a> &nbsp; <a href="/download/{{ v }}">Download</a></span></li>{% endfor %}</ul>
</section>{% endif %}
</div>
</body></html>
"""

RESULT = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Your video</title>
<meta name="description" content="Your rendered equation video, ready to watch and download.">
<link href="https://fonts.googleapis.com/css2?family=Mona+Sans:wdth,wght@100,400;100,500;125,300&display=swap" rel="stylesheet">
<style>
/* Hallmark · shape: app screen · genre: atmospheric · theme: Midnight (deal 1/3, seed equation-cinematic-video-generator-13d1·f51d8f6a·2026-11-07·r0)
 * nav: none · signature: the video player · states: default, hover, focus-visible, active, disabled
 * axes: dark/grotesk-sans/cool · posture: committed · contrast: pass · v2.0.0 */
/* Hallmark · pre-emit critique: P_ H_ E_ S_ R_ V_ · weakest: _, <what you did about it> */
:root {
  color-scheme: dark;
  --space-3xs: 2px; --space-2xs: 4px; --space-xs: 8px; --space-sm: 12px; --space-md: 16px; --space-lg: 24px; --space-xl: 40px; --space-2xl: 64px; --space-3xl: 96px; --space-4xl: 144px;
  --text-xs: 0.75rem; --text-sm: 0.875rem; --text-md: 1rem; --text-lg: 1.2rem; --text-xl: 1.44rem; --text-2xl: 1.728rem; --text-3xl: 2.074rem;
  --text-display-s: 1.44rem; --text-display: 1.728rem; --text-section: 1.2rem; --text-title: 1rem; --text-lead: 1rem;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1); --ease-in: cubic-bezier(0.7, 0, 0.84, 0); --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-micro: 120ms; --dur-short: 220ms; --dur-long: 420ms;
  --color-error: oklch(72% 0.15 27); --color-success: oklch(76% 0.13 150);
  --color-paper: oklch(14% 0.048 264); --color-paper-2: oklch(18.5% 0.052 264); --color-paper-3: oklch(23% 0.055 264);
  --color-ink: oklch(95% 0.016 250); --color-ink-2: oklch(88% 0.05 245); --color-muted: oklch(73% 0.04 256);
  --color-rule: oklch(29% 0.058 264); --color-rule-2: oklch(40% 0.06 262);
  --color-accent: oklch(80% 0.11 230); --color-accent-2: oklch(58% 0.1 236); --color-accent-ink: oklch(16% 0.05 264); --color-focus: oklch(84% 0.12 228);
  --font-display: "Mona Sans", ui-sans-serif, system-ui, sans-serif; --font-body: var(--font-display); --font-outlier: var(--font-display);
  --radius-card: 0; --radius-pill: 0; --rule-hair: 1px;
  --shadow-card: 0 24px 48px -24px oklch(6% 0.04 264 / 0.7);
  --tracking-display: -0.015em; --display-weight: 300; --display-stretch: 125%;
}
*, *::before, *::after { box-sizing: border-box; }
html, body { overflow-x: clip; }
html { scrollbar-color: var(--color-muted) var(--color-paper); }
body { margin: 0; background: var(--color-paper); color: var(--color-ink); font-family: var(--font-body); font-size: var(--text-md); line-height: 1.55; -webkit-font-smoothing: antialiased; caret-color: var(--color-accent); }
::selection { background: color-mix(in oklab, var(--color-accent) 22%, transparent); color: var(--color-ink); }
:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
a { color: inherit; text-decoration-thickness: 1px; text-underline-offset: 0.16em; }
a:hover { text-decoration-color: var(--color-accent); }
h1, h2, h3 { margin: 0; font-family: var(--font-display); font-weight: var(--display-weight); font-stretch: var(--display-stretch); font-synthesis: none; letter-spacing: var(--tracking-display); line-height: 1.04; overflow-wrap: break-word; min-width: 0; text-wrap: balance; }
h1 { max-width: 20ch; font-size: var(--text-display); }
h2 { max-width: 30ch; font-size: var(--text-section); }
h3 { max-width: 40ch; font-size: var(--text-title); line-height: 1.2; font-weight: 500; }
.lead { font-size: var(--text-lead); line-height: 1.45; max-width: 52ch; color: var(--color-ink-2); }
p { margin: 0; text-wrap: pretty; }
p:not([class]) { max-width: 65ch; }
img, video { max-width: 100%; height: auto; display: block; }
svg { display: block; }
button, input, select, textarea { font: inherit; }
.shell { width: 100%; max-width: 960px; margin-inline: auto; padding-inline: var(--space-lg); padding-block: var(--space-xl) var(--space-2xl); }
.masthead { margin-bottom: var(--space-lg); }
.wordmark { display: flex; align-items: center; gap: var(--space-sm); }
.wordmark svg { width: 28px; height: 28px; flex: none; color: var(--color-accent); }
.wordmark h1 { font-size: var(--text-display); }
.masthead .lead { margin-top: var(--space-md); }
.settle { animation: settle var(--dur-long) var(--ease-out) both; }
@keyframes settle { from { opacity: 0.6; } }
video { width: 100%; background: var(--color-paper); }
.audio { background: var(--color-paper-2); padding: var(--space-md); margin-top: var(--space-md); }
.audio h2 { margin-bottom: var(--space-xs); }
.audio p { margin-bottom: var(--space-xs); color: var(--color-ink-2); }
.audio p:last-child { margin-bottom: 0; }
.audio .tip { font-size: var(--text-sm); color: var(--color-muted); }
.btn { display: inline-flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-lg); font-weight: 500; font-size: var(--text-md); border: var(--rule-hair) solid transparent; background: none; border-radius: var(--radius-pill); color: var(--color-ink); cursor: pointer; white-space: nowrap; text-decoration: none; transition: background-color var(--dur-short) var(--ease-out); }
.btn svg { width: 16px; height: 16px; flex: none; }
.btn--primary { background: var(--color-accent); color: var(--color-accent-ink); }
.btn--primary:hover { background: var(--color-accent-2); color: var(--color-accent-ink); }
.btn--secondary { border-color: var(--color-rule-2); }
.btn--secondary:hover { background: var(--color-paper-2); }
.btn:active { transform: translateY(1px); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.actions { display: flex; gap: var(--space-md); flex-wrap: wrap; align-items: center; margin-top: var(--space-md); }
.note { font-size: var(--text-sm); color: var(--color-muted); line-height: 1.6; margin-top: var(--space-md); }
@media (max-width: 40rem) {
  .shell { padding-inline: var(--space-md); }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; } }
</style>
</head><body>
<div class="shell">
<header class="masthead settle">
  <div class="wordmark">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5.5"/></svg>
    <h1>Your video is ready</h1>
  </div>
  {% if secs %}<p class="lead">{{ title }}, rendered in {{ secs }}s. Watch it here first:</p>{% else %}<p class="lead">{{ title }}. Watch it here first:</p>{% endif %}
</header>
{% if story %}<p class="note">{{ story }}</p>{% endif %}
<video controls muted autoplay loop playsinline preload="auto"{% if poster %} poster="{{ poster }}"{% endif %} src="/watch/{{ job }}"></video>
<div class="audio">
  <h2>Add this audio when you post</h2>
  <p>The video is silent.</p>
  <p>{{ audio.song }} by {{ audio.artist }} ({{ audio.language }})</p>
  <p>Use {{ audio.start_fmt }} to {{ audio.end_fmt }} (approx.), {{ audio.moment }}</p>
  <p>{{ audio.why }}</p>
  <p class="tip">{{ audio.tip }} Timestamps are approximate. Check the hook in Instagram’s music picker before posting.</p>
</div>
<div class="actions">
  <a class="btn btn--primary" href="/download/{{ job }}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M12 4v12M6 10l6 6 6-6M5 20h14"/></svg>Download video (.mp4)</a>
  <a class="btn btn--secondary" href="/"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>Render another equation</a>
</div>
<p class="note">Clicking Download saves equation-{{ job }}.mp4 to your device (usually your Downloads folder). The same file is also in the project’s outputs/ folder. Use the player above to preview (play, pause, scrub, or fullscreen) before you download.</p>
</div>
</body></html>
"""


def list_outputs():
    """Newest rendered videos first, names without .mp4, max 10."""
    try:
        files = [f for f in os.listdir(OUT_DIR) if f.endswith(".mp4")]
    except FileNotFoundError:
        return []
    files.sort(key=lambda f: os.path.getmtime(os.path.join(OUT_DIR, f)), reverse=True)
    return [f[:-4] for f in files[:10]]


@app.route("/", methods=["GET"])
def home():
    return render_template_string(PAGE, presets=PRESETS, error="", videos=list_outputs())


@app.route("/render", methods=["POST"])
def render():
    form = request.form
    preset = form.get("preset", "")
    try:
        if preset:
            cfg = config_from_preset(preset)
        else:
            mode = form.get("mode", "y")
            cfg = {"mode": mode, "color": form.get("color") or "#22d3ee",
                   "duration": float(form.get("duration") or 8),
                   "x_range": [-7, 7], "y_range": [-3, 3]}
            rmin = float(form.get("rmin") or -6.28)
            rmax = float(form.get("rmax") or 6.28)
            if mode == "y":
                cfg.update(expr=form.get("expr1") or "sin(x)", x_min=rmin, x_max=rmax,
                           title=f"y = {form.get('expr1')}",
                           latex="y = " + latex_of(form.get("expr1") or "sin(x)", "x"))
            elif mode == "parametric":
                cfg.update(x_expr=form.get("expr1") or "cos(t)",
                           y_expr=form.get("expr2") or "sin(t)",
                           t_min=rmin, t_max=rmax, x_range=[-2, 2], y_range=[-2, 2],
                           title="Parametric Curve",
                           latex="x(t)=" + latex_of(form.get("expr1") or "cos(t)", "t"))
            else:
                cfg.update(expr=form.get("expr1") or "2*sin(3*theta)",
                           t_min=rmin, t_max=rmax, x_range=[-3, 3], y_range=[-3, 3],
                           title=f"r = {form.get('expr1')}",
                           latex="r = " + latex_of(form.get("expr1") or "2*sin(3*theta)", "theta"))
        validate_config(cfg)
    except (ValueError, TypeError) as exc:
        return render_template_string(PAGE, presets=PRESETS, error=str(exc),
                                      videos=list_outputs()), 400
    cfg["camera_moves"] = form.get("camera", "on") != "off"
    cfg.setdefault("lap_time", None)

    job = uuid.uuid4().hex[:8]
    job_dir = os.path.join(JOBS_DIR, job)
    os.makedirs(job_dir, exist_ok=True)
    cfg_path = os.path.join(job_dir, "equation.json")
    save_config(cfg, cfg_path)
    quality = form.get("quality", "medium")
    qflag = {"low": "-ql", "medium": "-qm", "high": "-qh"}[quality]
    qdir = {"low": "480p15", "medium": "720p30", "high": "1080p60"}[quality]

    started = time.time()
    env = dict(os.environ, EQ_CONFIG=cfg_path)
    result = subprocess.run(
        [sys.executable, "-m", "manim", "render", qflag, "--format=mp4",
         "-o", job, "scene.py", "EquationCinema"],
        cwd=BASE, env=env, timeout=900,
    )
    if result.returncode != 0:
        return render_template_string(
            PAGE, presets=PRESETS, videos=list_outputs(),
            error="Manim failed to render. See README Troubleshooting — "
                  "if it mentions LaTeX, set MANIM_USE_TEX=0 and restart the server."), 500

    made = os.path.join(BASE, "media", "videos", "scene", qdir, f"{job}.mp4")
    dest = os.path.join(OUT_DIR, f"{job}.mp4")
    if os.path.exists(made):
        shutil.copyfile(made, dest)
    if not os.path.exists(dest):
        return render_template_string(PAGE, presets=PRESETS, videos=list_outputs(),
                                      error="Manim finished but the video file was not found."), 500
    audio = audio_for(cfg)
    audio = {**audio, "start_fmt": fmt_time(audio["start"]), "end_fmt": fmt_time(audio["end"])}
    poster = ""
    poster_path = os.path.join(OUT_DIR, f"{job}-poster.jpg")
    try:
        subprocess.run(["ffmpeg", "-y", "-ss", "1", "-i", dest, "-frames:v", "1", poster_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, check=True)
        if os.path.exists(poster_path):
            poster = f"/poster/{job}"
    except Exception:
        poster = ""
    return render_template_string(RESULT, job=job,
                                  title=cfg.get("title", "Equation"),
                                  story=cfg.get("story", ""),
                                  secs=int(time.time() - started), audio=audio, poster=poster)


@app.route("/result/<job>")
def result_page(job):
    """Re-open a past render's preview page (used by the home-page list)."""
    safe = "".join(c for c in job if c.isalnum() or c in "-_")
    if not os.path.exists(os.path.join(OUT_DIR, f"{safe}.mp4")):
        return "Video not found — render it again.", 404
    audio = audio_for({"audio": "calm"})
    audio = {**audio, "start_fmt": fmt_time(audio["start"]), "end_fmt": fmt_time(audio["end"])}
    poster = f"/poster/{safe}" if os.path.exists(os.path.join(OUT_DIR, f"{safe}-poster.jpg")) else ""
    return render_template_string(RESULT, job=safe, title=safe, story="", secs=0, audio=audio, poster=poster)


@app.route("/watch/<job>")
def watch(job):
    """Stream the video for the in-browser preview player (no download)."""
    safe = "".join(c for c in job if c.isalnum() or c in "-_")
    path = os.path.join(OUT_DIR, f"{safe}.mp4")
    if not os.path.exists(path):
        return "Video not found — render it again.", 404
    return send_file(path, as_attachment=False, mimetype="video/mp4")


@app.route("/poster/<job>")
def poster(job):
    """Still frame for the result page's video poster (gate 28b)."""
    safe = "".join(c for c in job if c.isalnum() or c in "-_")
    path = os.path.join(OUT_DIR, f"{safe}-poster.jpg")
    if not os.path.exists(path):
        return "Poster not found.", 404
    return send_file(path, as_attachment=False, mimetype="image/jpeg")


@app.route("/download/<job>")
def download(job):
    safe = "".join(c for c in job if c.isalnum() or c in "-_")
    path = os.path.join(OUT_DIR, f"{safe}.mp4")
    if not os.path.exists(path):
        return "Video not found — render it again.", 404
    return send_file(path, as_attachment=True, download_name=f"equation-{safe}.mp4")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"Open http://127.0.0.1:{port} in your browser")
    app.run(host="0.0.0.0", port=port)

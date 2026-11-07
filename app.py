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
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Manim Equation Cinema</title>
<style>
body{font-family:system-ui,sans-serif;background:#050510;color:#e2e8f0;max-width:760px;margin:0 auto;padding:24px}
h1{font-size:28px} label{display:block;margin:14px 0 4px;color:#94a3b8}
input,select{width:100%;padding:10px;border-radius:8px;border:1px solid #334155;background:#0f172a;color:#fff;font-size:16px}
button{margin-top:18px;padding:12px 22px;border:0;border-radius:10px;background:#22d3ee;color:#050510;font-weight:700;font-size:16px;cursor:pointer}
a{color:#22d3ee} .err{background:#450a0a;padding:12px;border-radius:8px} .ok{background:#052e16;padding:12px;border-radius:8px}
small{color:#94a3b8} .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
</style></head><body>
<h1>🎬 Manim Equation Cinema</h1>
<p>Type any equation. Manim draws it cinematically and you download the video.</p>
{% if error %}<div class="err">{{ error }}</div>{% endif %}
<form method="post" action="/render">
  <label>Preset (or choose Custom below)</label>
  <select name="preset"><option value="">Custom — use the fields below</option>
  {% for k,v in presets.items() %}<option value="{{ k }}">{{ v.label }} — viral {{ v.viral }}/5</option>{% endfor %}</select>
  <label>Mode</label>
  <select name="mode"><option value="y">y = f(x)</option><option value="parametric">Parametric x(t), y(t)</option><option value="polar">Polar r(θ)</option></select>
  <div class="row"><div><label>y = / r = / x(t) =</label><input name="expr1" value="sin(x)" placeholder="sin(x)"></div>
  <div><label>y(t) = (parametric only)</label><input name="expr2" value="sin(t)" placeholder="sin(t)"></div></div>
  <div class="row"><div><label>Range from</label><input name="rmin" value="-6.28"></div>
  <div><label>Range to</label><input name="rmax" value="6.28"></div></div>
  <div class="row"><div><label>Draw time (seconds)</label><input name="duration" value="8"></div>
  <div><label>Colour</label><input name="color" value="#22d3ee"></div></div>
  <div class="row"><div><label>Quality</label><select name="quality"><option value="medium">720p (recommended)</option><option value="low">480p (fast test)</option><option value="high">1080p (slow)</option></select></div>
  <div><label>Camera movement</label><select name="camera"><option value="on">On — slow zoom (cinematic)</option><option value="off">Off — fixed camera</option></select></div></div>
  <button type="submit">▶ Render video (takes 30s – a few minutes)</button>
</form>
<p><small>Examples to try: <b>y = sin(x)</b> &nbsp;·&nbsp; <b>y = x^2 / 4</b> &nbsp;·&nbsp; parametric <b>cos(t), sin(t)</b> &nbsp;·&nbsp; polar <b>2*sin(3*theta)</b> &nbsp;·&nbsp; preset <b>Butterfly</b></small></p>
<p><small>Videos are saved in the <b>outputs/</b> folder too. The video itself is silent — after rendering you get a song suggestion (name + timestamps) to add in Instagram / CapCut.</small></p>
<h2 style="font-size:18px;margin-top:28px">Most viral presets — try these first</h2>
<ul>{% for k,v in presets.items() %}{% if v.viral >= 5 %}<li><b>{{ v.label }}</b> — {{ v.story or v.why }}</li>{% endif %}{% endfor %}</ul>
{% if videos %}<h2 style="font-size:18px;margin-top:28px">Your videos — click to preview</h2>
<ul>{% for v in videos %}<li><a href="/result/{{ v }}">{{ v }}.mp4</a> &nbsp;·&nbsp; <a href="/download/{{ v }}">Download</a></li>{% endfor %}</ul>{% endif %}
</body></html>
"""

RESULT = """
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Your video</title>
<style>body{font-family:system-ui,sans-serif;background:#050510;color:#e2e8f0;max-width:760px;margin:0 auto;padding:24px}
a{color:#22d3ee} video{width:100%;border-radius:12px;background:#000}
button{margin-top:14px;padding:12px 22px;border:0;border-radius:10px;background:#22d3ee;color:#050510;font-weight:700;font-size:16px;cursor:pointer}
.btn2{background:#1e293b;color:#e2e8f0} small{color:#94a3b8} .audio{background:#0f172a;border:1px solid #334155;border-radius:12px;padding:14px;margin-top:16px}</style>
</head><body><h1>✅ Your video is ready</h1><p>{{ title }} — rendered in {{ secs }}s. Watch it here first:</p>
{% if story %}<p><small>📖 {{ story }}</small></p>{% endif %}
<video controls autoplay loop playsinline preload="auto" src="/watch/{{ job }}"></video>
<div class="audio"><b>🎵 Add this audio when you post (video is silent):</b><br>
{{ audio.song }} — {{ audio.artist }} ({{ audio.language }})<br>
Use <b>{{ audio.start_fmt }}–{{ audio.end_fmt }}</b> (approx.) — {{ audio.moment }}<br>
{{ audio.why }}<br><small>{{ audio.tip }} Timestamps are approximate — check the hook in Instagram's music picker before posting.</small></div>
<p><a href="/download/{{ job }}"><button>⬇ Download video (.mp4)</button></a>
&nbsp;<a href="/"><button class="btn2">← Render another equation</button></a></p>
<p><small>Clicking Download saves <b>equation-{{ job }}.mp4</b> to your device (usually your Downloads folder). The same file is also in the project's <b>outputs/</b> folder. Use the player above to preview — play, pause, scrub, or fullscreen — before you download.</small></p>
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
    return render_template_string(RESULT, job=job,
                                  title=cfg.get("title", "Equation"),
                                  story=cfg.get("story", ""),
                                  secs=int(time.time() - started), audio=audio)


@app.route("/result/<job>")
def result_page(job):
    """Re-open a past render's preview page (used by the home-page list)."""
    safe = "".join(c for c in job if c.isalnum() or c in "-_")
    if not os.path.exists(os.path.join(OUT_DIR, f"{safe}.mp4")):
        return "Video not found — render it again.", 404
    audio = audio_for({"audio": "calm"})
    audio = {**audio, "start_fmt": fmt_time(audio["start"]), "end_fmt": fmt_time(audio["end"])}
    return render_template_string(RESULT, job=safe, title=safe, story="", secs=0, audio=audio)


@app.route("/watch/<job>")
def watch(job):
    """Stream the video for the in-browser preview player (no download)."""
    safe = "".join(c for c in job if c.isalnum() or c in "-_")
    path = os.path.join(OUT_DIR, f"{safe}.mp4")
    if not os.path.exists(path):
        return "Video not found — render it again.", 404
    return send_file(path, as_attachment=False, mimetype="video/mp4")


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

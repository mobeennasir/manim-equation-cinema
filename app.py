"""
app.py — web server: type an equation in your browser, get a video.

Run:   python app.py
Open:  http://127.0.0.1:5000

How it works:
1. You open the site and type an equation (or pick a preset), then click
   Render. The server starts the render in the background and answers
   at once with a loading page, so the request never hangs.
2. The loading page polls the job status every few seconds. When the
   video is saved, it takes you to the result page with the finished
   video playing right there in the browser (an embedded <video>
   player — play, pause, scrub, fullscreen).
3. Under the player is a Download button. Clicking it saves the .mp4
   to your device (Downloads folder). The same file is also in outputs/.

Why the loading page exists: the old version held one HTTP request
open until Manim finished, and the gateway in front of the live site
cuts requests off at about 100 seconds, so the user got a 504 and
never saw the video even though it had been saved. The render now
runs in a background thread and the browser polls for it, so no
request ever waits on Manim.

Deploy note: this same file is what Koyeb runs (see Dockerfile).
On a free host, rendering is slow — the loading page says so honestly.
"""

import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid

import numpy as np
from flask import Flask, jsonify, redirect, render_template_string, request, send_file, url_for

from audio import audio_for, fmt_time
from equations import (
    PRESETS,
    config_from_preset,
    curves_from_config,
    latex_of,
    load_config,
    lorenz_points,
    make_function,
    save_config,
    validate_config,
)

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "outputs")
JOBS_DIR = os.path.join(BASE, "jobs")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(JOBS_DIR, exist_ok=True)

app = Flask(__name__)


# --------------------------------------------------------------------------
# Equation thumbnails: small SVG plots of the real equations, drawn from the
# same sampling the videos use. No stock art, no invented shapes.
# --------------------------------------------------------------------------

def _darken(hex_color, factor=0.72):
    """Deepen a preset colour so its line stays visible on a light page."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, TypeError):
        return "#2b6cb0"
    return "#%02x%02x%02x" % (int(r * factor), int(g * factor), int(b * factor))


def _sample_curve(curve, n=400):
    """Return (xs, ys) arrays for one curve dict, or None if not plottable."""
    mode = curve.get("mode")
    try:
        if mode == "y":
            _, f = make_function(curve["expr"], "x")
            xs = np.linspace(float(curve.get("x_min", -6)), float(curve.get("x_max", 6)), n)
            ys = np.asarray(f(xs), dtype=float)
        elif mode == "parametric":
            _, fx = make_function(curve["x_expr"], "t")
            _, fy = make_function(curve["y_expr"], "t")
            t = np.linspace(float(curve.get("t_min", 0)), float(curve.get("t_max", 6.28)), n)
            xs = np.asarray(fx(t), dtype=float)
            ys = np.asarray(fy(t), dtype=float)
        elif mode == "polar":
            _, f = make_function(curve["expr"], "theta")
            t = np.linspace(float(curve.get("t_min", 0)), float(curve.get("t_max", 6.28)), n)
            r = np.asarray(f(t), dtype=float)
            xs, ys = r * np.cos(t), r * np.sin(t)
        elif mode == "lorenz":
            xs, ys = lorenz_points(n=500)
        else:
            return None
    except Exception:
        return None
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    keep = np.isfinite(xs) & np.isfinite(ys) & (np.abs(xs) < 60) & (np.abs(ys) < 60)
    if keep.sum() < 4:
        return None
    return xs[keep], ys[keep]


def _points_to_path(xs, ys, w, h, pad=8):
    """Map data points to an SVG path string, breaking on big jumps."""
    xmin, xmax = float(xs.min()), float(xs.max())
    ymin, ymax = float(ys.min()), float(ys.max())
    if xmax - xmin < 1e-9:
        xmax = xmin + 1
    if ymax - ymin < 1e-9:
        ymax = ymin + 1
    s = min((w - 2 * pad) / (xmax - xmin), (h - 2 * pad) / (ymax - ymin))
    ox = pad + ((w - 2 * pad) - s * (xmax - xmin)) / 2 - s * xmin
    oy = pad + ((h - 2 * pad) - s * (ymax - ymin)) / 2 + s * ymax
    parts, prev = [], None
    for x, y in zip(xs, ys):
        X, Y = ox + s * float(x), oy - s * float(y)
        if prev is None or ((X - prev[0]) ** 2 + (Y - prev[1]) ** 2) ** 0.5 > 0.4 * min(w, h):
            parts.append(f"M{X:.1f},{Y:.1f}")
        else:
            parts.append(f"L{X:.1f},{Y:.1f}")
        prev = (X, Y)
    return " ".join(parts)


def _curve_elements(curve, w, h, draw=False):
    """SVG elements for one curve dict. Returns a list of element strings."""
    color = _darken(curve.get("color", "#22d3ee"))
    mode = curve.get("mode")
    if mode == "chords":
        n = int(curve.get("points", 200))
        m = int(curve.get("multiple", 3))
        cx, cy, R = w / 2, h / 2, min(w, h) / 2 - 8
        pts = [(cx + R * math.cos(2 * math.pi * i / n),
                cy + R * math.sin(2 * math.pi * i / n)) for i in range(n)]
        out = [f'<circle cx="{cx}" cy="{cy}" r="{R:.1f}" fill="none" stroke="{color}" stroke-width="1.2"/>']
        step = max(1, n // 60)
        for i in range(0, n, step):
            x1, y1 = pts[i]
            x2, y2 = pts[(i * m) % n]
            out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                       f'stroke="{color}" stroke-width="0.7" opacity="0.45"/>')
        return out
    if mode == "dots":
        n = int(curve.get("n", 600))
        angle = float(curve.get("angle", 137.508))
        spacing = float(curve.get("spacing", 0.12))
        pts = []
        for k in range(min(n, 220)):
            a = math.radians(k * angle)
            r_ = spacing * math.sqrt(k)
            pts.append((r_ * math.cos(a), r_ * math.sin(a)))
        if not pts:
            return []
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
        s = (min(w, h) - 16) / span
        cx = w / 2 - s * (min(xs) + max(xs)) / 2
        cy = h / 2 + s * (min(ys) + max(ys)) / 2
        return [f'<circle cx="{cx + s * x:.1f}" cy="{cy - s * y:.1f}" r="1.6" fill="{color}"/>'
                for x, y in pts]
    pts = _sample_curve(curve)
    if pts is None:
        return []
    d = _points_to_path(pts[0], pts[1], w, h)
    if not d:
        return []
    draw_attr = f' class="{draw}" pathLength="100"' if draw else ""
    return [f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"{draw_attr}/>']


def config_svg(cfg, w=320, h=200, draw=False):
    """One inline SVG plotting every curve of a config. Empty string on failure."""
    try:
        curves = curves_from_config(cfg)
    except Exception:
        return ""
    elements = []
    for curve in curves:
        elements.extend(_curve_elements(curve, w, h, draw=draw))
    if not elements:
        color = _darken(cfg.get("color", "#22d3ee"))
        elements = [f'<circle cx="{w / 2}" cy="{h / 2}" r="{min(w, h) / 4:.0f}" fill="none" '
                    f'stroke="{color}" stroke-width="2"/>']
    inner = "".join(elements)
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-hidden="true" xmlns="http://www.w3.org/2000/svg">{inner}</svg>')


def preset_svg(name, w=320, h=200, draw=False):
    """SVG thumbnail for a preset, by name."""
    try:
        return config_svg(config_from_preset(name), w, h, draw=draw)
    except Exception:
        return ""


# Built once at startup: every preset's thumbnail, so pages stay fast.
THUMBS = {}
for _name in PRESETS:
    _svg = preset_svg(_name)
    if _svg:
        THUMBS[_name] = _svg
HERO_SVG = preset_svg("butterfly", 520, 360, draw="draw")


# --------------------------------------------------------------------------
# Render jobs: background threads + a status file on disk, so no request
# ever waits on Manim and any worker can read the state.
# --------------------------------------------------------------------------

def _status_path(job):
    return os.path.join(JOBS_DIR, job, "status.json")


def _write_status(job, state, **extra):
    try:
        with open(_status_path(job), "w") as fh:
            json.dump({"state": state, **extra}, fh)
    except OSError:
        pass


def _read_status(job):
    try:
        with open(_status_path(job)) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _run_job(job, cfg, cfg_path, quality):
    """Render one job in a background thread; record done/error on disk."""
    qflag = {"low": "-ql", "medium": "-qm", "high": "-qh"}[quality]
    qdir = {"low": "480p15", "medium": "720p30", "high": "1080p60"}[quality]
    started = time.time()
    try:
        env = dict(os.environ, EQ_CONFIG=cfg_path)
        result = subprocess.run(
            [sys.executable, "-m", "manim", "render", qflag, "--format=mp4",
             "-o", job, "scene.py", "EquationCinema"],
            cwd=BASE, env=env, timeout=900,
        )
        if result.returncode != 0:
            raise RuntimeError("Manim failed to render this equation.")
        made = os.path.join(BASE, "media", "videos", "scene", qdir, f"{job}.mp4")
        dest = os.path.join(OUT_DIR, f"{job}.mp4")
        if os.path.exists(made):
            shutil.copyfile(made, dest)
        if not os.path.exists(dest):
            raise RuntimeError("Manim finished but the video file was not found.")
        try:
            with open(os.path.join(OUT_DIR, f"{job}.json"), "w") as fh:
                json.dump({"title": cfg.get("title", job)}, fh)
        except OSError:
            pass
        poster = ""
        poster_path = os.path.join(OUT_DIR, f"{job}-poster.jpg")
        try:
            grab_at = max(1.0, float(cfg.get("duration", 8)) * 0.4)
            subprocess.run(["ffmpeg", "-y", "-ss", str(grab_at), "-i", dest, "-frames:v", "1", poster_path],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=60, check=True)
            if os.path.exists(poster_path):
                poster = f"/poster/{job}"
        except Exception:
            poster = ""
        _write_status(job, "done", secs=int(time.time() - started), poster=poster,
                      title=cfg.get("title", job))
    except Exception as exc:  # noqa: BLE001 - the message is shown to the user
        _write_status(job, "error", message=str(exc)[:300], title=cfg.get("title", job))
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_JOBS.discard(job)


# --------------------------------------------------------------------------
# Semantic caching: the same request always renders the same video, so the
# output filename IS the hash of the request. A repeat request finds the
# file in outputs/ and is served at once, never re-rendered.
# --------------------------------------------------------------------------

import hashlib  # noqa: E402 - kept beside the cache code it serves

_ACTIVE_JOBS = set()
_ACTIVE_LOCK = threading.Lock()


def cache_key_for(form, preset, cfg):
    """Stable id for one render request: preset or full custom equation."""
    if preset:
        parts = ["preset", preset]
    else:
        parts = ["custom", form.get("mode", "y"), form.get("expr1", ""),
                 form.get("expr2", ""), form.get("rmin", ""), form.get("rmax", ""),
                 form.get("duration", ""), form.get("color", "")]
    parts += [form.get("quality", "medium"), form.get("camera", "on")]
    digest = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]
    return f"cache-{digest}"


def cached_video_path(key):
    """The saved video for a cache key, or None if it is not there."""
    path = os.path.join(OUT_DIR, f"{key}.mp4")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    return None


# --------------------------------------------------------------------------
# Janitor: every 30 minutes, delete rendered videos, posters, job folders
# and Manim's media files older than 1 hour. Renders in progress are
# never touched. Videos older than an hour are gone, so download any
# you want to keep.
# --------------------------------------------------------------------------

SWEEP_EVERY = 30 * 60
KEEP_FOR = 60 * 60


def _sweep_once(now=None):
    now = now or time.time()
    cutoff = now - KEEP_FOR
    with _ACTIVE_LOCK:
        busy = set(_ACTIVE_JOBS)
    for folder, suffixes in ((OUT_DIR, (".mp4", ".jpg", ".json")),
                             (os.path.join(BASE, "media"), (".mp4",))):
        try:
            names = os.listdir(folder)
        except FileNotFoundError:
            continue
        for name in names:
            if not name.endswith(suffixes):
                continue
            if any(b in name for b in busy):
                continue
            path = os.path.join(folder, name)
            try:
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                pass
    try:
        for name in os.listdir(JOBS_DIR):
            if name in busy:
                continue
            path = os.path.join(JOBS_DIR, name)
            try:
                if os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                pass
    except FileNotFoundError:
        pass


def _janitor():
    while True:
        time.sleep(SWEEP_EVERY)
        _sweep_once()


threading.Thread(target=_janitor, daemon=True, name="janitor").start()

STYLE = """
/* Hallmark · shape: app screen · genre: atmospheric · theme: Refract (deal 3/3, seed cinematic-equation-video-generator-78f9·f51d8f6a·2026-11-07·r0)
 * nav: wordmark + two anchors · signature: the butterfly drawing itself in the hero · states: default, hover, focus-visible, active, disabled · refract: water/pool
 * axes: light/grotesk-sans/cool · posture: restrained · contrast: pass · v2.0.0 */
/* Hallmark · pre-emit critique: P_ H_ E_ S_ R_ V_ · weakest: _, <what you did about it> */
:root {
  color-scheme: light;
  --space-3xs: 2px; --space-2xs: 4px; --space-xs: 8px; --space-sm: 12px; --space-md: 16px; --space-lg: 24px; --space-xl: 40px; --space-2xl: 64px; --space-3xl: 96px; --space-4xl: 144px;
  --text-xs: 0.75rem; --text-sm: 0.875rem; --text-md: 1rem; --text-lg: 1.2rem; --text-xl: 1.44rem; --text-2xl: 1.728rem; --text-3xl: 2.074rem;
  --text-display-s: 1.44rem; --text-display: 1.728rem; --text-section: 1.2rem; --text-title: 1rem; --text-lead: 1rem;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1); --ease-in: cubic-bezier(0.7, 0, 0.84, 0); --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-micro: 120ms; --dur-short: 220ms; --dur-long: 420ms;
  --color-error: oklch(52% 0.19 27); --color-success: oklch(50% 0.12 150);
  --container: 1440px; --gutter: 64px; --gap-columns: 32px; --section-gap-s: 120px; --section-gap: 144px; --section-gap-l: 176px;
  --z-base: 1; --z-raised: 10; --z-dropdown: 100; --z-sticky: 200; --z-sticky-nav: 300; --z-modal: 400; --z-toast: 500; --z-tooltip: 600;
  --color-paper: oklch(98.2% 0.006 95); --color-paper-2: oklch(96.4% 0.006 95); --color-paper-3: oklch(93.6% 0.008 95);
  --color-ink: oklch(23% 0.035 245); --color-ink-2: oklch(36% 0.035 245); --color-muted: oklch(50% 0.025 240);
  --color-rule: oklch(89.5% 0.008 230); --color-rule-2: oklch(93.5% 0.006 230);
  --color-accent: oklch(50% 0.12 234); --color-accent-hi: oklch(44% 0.12 236); --color-accent-ink: oklch(99% 0.003 95); --color-accent-soft: oklch(94% 0.025 220); --color-focus: oklch(56% 0.14 234);
  --color-shade: oklch(86% 0.05 212); --color-shade-2: oklch(74% 0.07 220); --color-light: oklch(99.7% 0.004 95);
  --spec-1: oklch(78% 0.15 32); --spec-2: oklch(90% 0.15 105); --spec-3: oklch(82% 0.13 175); --spec-4: oklch(66% 0.15 270);
  --color-slot: oklch(86% 0.05 212);
  --edge-light: inset 0 1px 0 oklch(100% 0 0 / 0.9), inset 0 0 0 1px oklch(100% 0 0 / 0.55);
  --shadow-card: 18px 28px 48px -26px oklch(52% 0.09 220 / 0.38), 2px 3px 6px -2px oklch(40% 0.05 230 / 0.12);
  --shadow-cast: 28px 40px 70px -30px oklch(60% 0.11 212 / 0.45);
  --font-display: "Funnel Display", ui-sans-serif, system-ui, sans-serif; --font-body: "Funnel Sans", ui-sans-serif, system-ui, sans-serif;
  --radius-card: 22px; --radius-inner: 12px; --radius-pill: 999px; --rule-hair: 1px;
  --tracking-display: -0.032em; --display-weight: 400;
}
*, *::before, *::after { box-sizing: border-box; }
html, body { overflow-x: clip; }
html { scrollbar-color: var(--color-muted) var(--color-paper); scroll-padding-top: var(--space-3xl); }
body { margin: 0; background: var(--color-paper); color: var(--color-ink); font-family: var(--font-body); font-size: 17px; line-height: 1.6; -webkit-font-smoothing: antialiased; caret-color: var(--color-accent); }
::selection { background: color-mix(in oklab, var(--color-accent) 22%, transparent); color: var(--color-ink); }
:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
a { color: inherit; text-decoration-thickness: 1px; text-underline-offset: 0.16em; }
a:hover { text-decoration-color: var(--color-accent); }
h1, h2, h3 { margin: 0; font-family: var(--font-display); font-weight: var(--display-weight); font-synthesis: none; letter-spacing: var(--tracking-display); line-height: 1.02; overflow-wrap: break-word; min-width: 0; text-wrap: balance; }
h1 { max-width: 20ch; font-size: var(--text-display); }
h2 { max-width: 30ch; font-size: var(--text-section); }
h3 { max-width: 40ch; font-size: var(--text-title); line-height: 1.2; font-weight: 500; }
.lead { font-size: var(--text-lead); line-height: 1.45; max-width: 52ch; }
p { margin: 0; text-wrap: pretty; }
p:not([class]) { max-width: 65ch; }
img, video { max-width: 100%; height: auto; display: block; }
svg { display: block; }
[hidden] { display: none !important; }
button, input, select, textarea { font: inherit; }
.num, .figure, td.num { font-variant-numeric: tabular-nums; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.shell { width: 100%; max-width: 1200px; margin-inline: auto; padding-inline: var(--gutter); padding-block: 0 var(--space-2xl); }
.topbar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-md); padding-top: var(--space-md); padding-bottom: var(--space-md); }
.wordmark { display: flex; align-items: center; gap: var(--space-sm); font-family: var(--font-display); font-weight: 500; font-size: var(--text-lg); color: var(--color-ink); text-decoration: none; }
.wordmark svg { width: 28px; height: 28px; flex: none; color: var(--color-accent); }
.topnav { display: flex; gap: var(--space-lg); }
.topnav a { font-size: var(--text-sm); font-weight: 500; color: var(--color-muted); text-decoration: none; }
.topnav a:hover { color: var(--color-ink); }
.hero { position: relative; display: grid; grid-template-columns: 1.05fr 0.95fr; gap: var(--space-2xl); align-items: center; padding-block: var(--space-2xl); }
.hero h1 { font-size: clamp(2.074rem, 4.5vw, 3rem); }
.hero .lead { margin-top: var(--space-md); font-size: var(--text-lg); color: var(--color-muted); }
.hero-actions { display: flex; gap: var(--space-md); flex-wrap: wrap; margin-top: var(--space-lg); }
.hero-art { position: relative; }
.light { position: absolute; inset: -60px -30px; width: calc(100% + 60px); height: calc(100% + 120px); pointer-events: none; -webkit-mask-image: linear-gradient(to right, transparent 20%, var(--color-ink) 65%); mask-image: linear-gradient(to right, transparent 20%, var(--color-ink) 65%); }
.clear { background: color-mix(in oklab, var(--color-light) 80%, transparent); border-radius: var(--radius-card); box-shadow: var(--edge-light), var(--shadow-card); }
.hero-panel { position: relative; padding: var(--space-lg); box-shadow: var(--edge-light), var(--shadow-cast); }
.hero-panel svg { width: 100%; height: auto; }
.hero-panel .caption { margin-top: var(--space-sm); font-size: var(--text-sm); color: var(--color-muted); text-align: center; }
.draw { stroke-dasharray: 100; stroke-dashoffset: 100; animation: draw 7s var(--ease-out) both; }
.draw-loop { stroke-dasharray: 100; stroke-dashoffset: 100; animation: drawloop 6s var(--ease-out) infinite; }
@keyframes draw { to { stroke-dashoffset: 0; } }
@keyframes drawloop { 0% { stroke-dashoffset: 100; } 70% { stroke-dashoffset: 0; } 100% { stroke-dashoffset: 0; } }
.settle { animation: settle var(--dur-long) var(--ease-out) both; }
@keyframes settle { from { opacity: 0.6; } }
.btn { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-xs); min-height: 48px; padding: 0 var(--space-lg); border: 0; border-radius: var(--radius-pill); background: var(--color-accent); color: var(--color-accent-ink); font: 500 var(--text-md)/1 var(--font-body); cursor: pointer; white-space: nowrap; text-decoration: none; box-shadow: var(--edge-light), var(--shadow-card); transition: background-color var(--dur-short) var(--ease-out), transform var(--dur-short) var(--ease-out), box-shadow var(--dur-short) var(--ease-out); }
.btn:hover { background: var(--color-accent-hi); }
.btn svg { width: 16px; height: 16px; flex: none; }
.btn--clear { background: color-mix(in oklab, var(--color-light) 80%, transparent); color: var(--color-ink); box-shadow: var(--edge-light), var(--shadow-card); }
.btn--clear:hover { background: var(--color-light); }
.btn:active { transform: translateY(1px); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
section { margin-bottom: var(--space-2xl); }
section > .lead { margin-top: var(--space-xs); margin-bottom: var(--space-lg); }
.workbench { padding: var(--space-xl); margin-bottom: var(--space-2xl); }
.workbench h2 { margin-bottom: var(--space-md); }
.err { background: var(--color-paper-3); border-left: 2px solid var(--color-error); padding: var(--space-md); margin-bottom: var(--space-lg); border-radius: var(--radius-inner); }
.field { margin-bottom: var(--space-md); }
.field:last-child { margin-bottom: 0; }
label { display: block; font-size: var(--text-sm); font-weight: 500; color: var(--color-muted); margin-bottom: var(--space-xs); }
input, select { width: 100%; padding: var(--space-sm) var(--space-md); background: var(--color-light); border: var(--rule-hair) solid var(--color-rule); border-radius: var(--radius-inner); color: var(--color-ink); font-size: var(--text-md); }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-md); }
.hint { font-size: var(--text-sm); color: var(--color-muted); margin-top: var(--space-xs); }
.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--space-lg); list-style: none; margin: 0; padding: 0; }
.card { display: block; border-radius: var(--radius-card); background: color-mix(in oklab, var(--color-light) 80%, transparent); box-shadow: var(--edge-light), var(--shadow-card); color: inherit; text-decoration: none; overflow: hidden; transition: transform var(--dur-short) var(--ease-out), box-shadow var(--dur-short) var(--ease-out); }
.card:hover { transform: translateY(-2px); box-shadow: var(--edge-light), var(--shadow-cast); }
.card .thumb { background: var(--color-paper-2); padding: var(--space-md); }
.card .thumb svg { width: 100%; height: auto; }
.card .card-body { padding: var(--space-md) var(--space-lg) var(--space-lg); }
.card h3 { margin-bottom: var(--space-2xs); }
.card p { font-size: var(--text-sm); color: var(--color-muted); }
.card .viral { display: inline-block; margin-top: var(--space-sm); font-size: var(--text-sm); font-weight: 500; color: var(--color-accent); }
.rows { list-style: none; margin: 0; padding: 0; }
.rows li { display: flex; justify-content: space-between; align-items: center; gap: var(--space-md); padding-top: var(--space-sm); padding-bottom: var(--space-sm); border-top: var(--rule-hair) solid var(--color-rule); }
.rows li:last-child { border-bottom: var(--rule-hair) solid var(--color-rule); }
.row-title { font-weight: 500; flex: none; }
.rows .row-text { color: var(--color-ink-2); text-align: right; }
.rows code { font-variant-numeric: tabular-nums; }
.note { font-size: var(--text-sm); color: var(--color-muted); line-height: 1.6; margin-bottom: var(--space-xl); }
.rows li.video-row { display: grid; grid-template-columns: 96px minmax(0, 1fr) auto; gap: var(--space-md); align-items: center; }
.thumb-sm { width: 96px; height: 54px; object-fit: cover; border-radius: var(--radius-inner); flex: none; background: var(--color-paper-2); }
.thumb-ph { width: 96px; height: 54px; border-radius: var(--radius-inner); flex: none; background: var(--color-paper-2); display: flex; align-items: center; justify-content: center; color: var(--color-muted); }
.thumb-ph svg { width: 20px; height: 20px; }
.video-panel { padding: var(--space-md); box-shadow: var(--edge-light), var(--shadow-cast); margin-bottom: var(--space-lg); }
.video-panel video { width: 100%; border-radius: var(--radius-inner); background: var(--color-ink); color: var(--color-accent-ink); }
.audio { background: var(--color-paper-2); border-radius: var(--radius-inner); padding: var(--space-md); margin-top: var(--space-md); }
.audio h2 { margin-bottom: var(--space-xs); }
.audio p { margin-bottom: var(--space-xs); color: var(--color-ink-2); }
.audio p:last-child { margin-bottom: 0; }
.audio .tip { font-size: var(--text-sm); color: var(--color-muted); }
.actions { display: flex; gap: var(--space-md); flex-wrap: wrap; align-items: center; margin-top: var(--space-md); }
.waiting { max-width: 720px; margin-inline: auto; text-align: center; padding-block: var(--space-2xl); }
.waiting .curve { max-width: 420px; margin: 0 auto var(--space-lg); }
.waiting .curve svg { width: 100%; height: auto; }
.waiting h1 { margin-inline: auto; }
.waiting .lead { margin: var(--space-md) auto 0; }
.meter { height: 2px; background: var(--color-rule-2); border-radius: 999px; overflow: hidden; margin: var(--space-lg) auto; max-width: 420px; }
.meter > span { display: block; height: 100%; width: 0; background: var(--color-accent); }
.waiting .meta { font-size: var(--text-sm); color: var(--color-muted); font-variant-numeric: tabular-nums; }
.waiting .stage { font-size: var(--text-lg); color: var(--color-ink-2); margin-top: var(--space-md); }
.footer { border-top: var(--rule-hair) solid var(--color-rule); padding-top: var(--space-lg); padding-bottom: var(--space-lg); font-size: var(--text-sm); color: var(--color-muted); display: flex; justify-content: space-between; gap: var(--space-md); flex-wrap: wrap; }
@media (max-width: 60rem) {
  :root { --gutter: 24px; --section-gap-s: 80px; --section-gap: 96px; --section-gap-l: 120px; }
  .hero { grid-template-columns: 1fr; gap: var(--space-lg); padding-block: var(--space-lg); }
}
@media (max-width: 40rem) {
  :root { --gutter: 16px; --section-gap-s: 56px; --section-gap: 72px; --section-gap-l: 96px; --gap-columns: 16px; }
  .shell { padding-inline: var(--space-md); }
  .row { grid-template-columns: 1fr; }
  .topnav { display: none; }
  .rows li.video-row { grid-template-columns: 64px minmax(0, 1fr); }
  .video-row .row-text { grid-column: 2; text-align: left; }
  .thumb-sm, .thumb-ph { width: 64px; height: 36px; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; } }
"""

PAGE = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Manim Equation Cinema</title>
<meta name="description" content="Type any equation and Manim draws it cinematically as a video you can download.">
<link href="https://fonts.googleapis.com/css2?family=Funnel+Display:wght@300;400;500&family=Funnel+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>{{ style | safe }}</style></head><body>
<div class="shell">
<header class="topbar">
  <a class="wordmark" href="/">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="4"/><path d="M3 9h18M7 5l2.5 4M12 5l2.5 4M17 5l2.5 4"/></svg>
    Manim Equation Cinema
  </a>
  <nav class="topnav" aria-label="Sections">
    <a href="#presets">Presets</a>
    <a href="#videos">Your videos</a>
  </nav>
</header>
<section class="hero" aria-label="Introduction">
  <div class="hero-text settle">
    <h1>Any equation, drawn like cinema.</h1>
    <p class="lead">Type an equation, pick a preset, and Manim draws it as a cinematic video you can download and post.</p>
    <div class="hero-actions">
      <a class="btn" href="#render">Render a video</a>
      <a class="btn btn--clear" href="#presets">Browse the presets</a>
    </div>
  </div>
  <div class="hero-art">
    <svg class="light" viewBox="0 0 600 400" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
      <g transform="rotate(-18 300 200)" opacity="0.35">
        <rect x="380" y="-100" width="46" height="600" style="fill: var(--spec-1)"/>
        <rect x="436" y="-100" width="34" height="600" style="fill: var(--spec-2)"/>
        <rect x="480" y="-100" width="26" height="600" style="fill: var(--spec-3)"/>
        <rect x="516" y="-100" width="18" height="600" style="fill: var(--spec-4)"/>
        <rect x="372" y="-100" width="4" height="600" style="fill: var(--color-light)"/>
      </g>
    </svg>
    <div class="clear hero-panel">
      {{ hero_svg | safe }}
      <p class="caption">The butterfly curve, drawn once, dot riding the tip.</p>
    </div>
  </div>
</section>
{% if error %}<div class="err" role="alert">{{ error }}</div>{% endif %}
<form id="render" method="post" action="/render">
  <section class="clear workbench" aria-label="Equation">
    <h2>Equation</h2>
    <div class="field">
      <label for="preset">Preset</label>
      <select id="preset" name="preset"><option value="">Custom: use the fields below</option>
      {% for k,v in presets.items() %}<option value="{{ k }}"{% if k == selected_preset %} selected{% endif %}>{{ v.label }} (viral {{ v.viral }}/5)</option>{% endfor %}</select>
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
  <section class="clear workbench" aria-label="Render settings">
    <h2>Render</h2>
    <div class="row">
      <div class="field"><label for="duration">Draw time (seconds)</label><input id="duration" name="duration" value="8"><p class="hint">How long the drawing takes.</p></div>
      <div class="field"><label for="color">Colour</label><input id="color" name="color" value="#22d3ee"></div>
    </div>
    <div class="row">
      <div class="field"><label for="quality">Quality</label><select id="quality" name="quality"><option value="medium">720p (recommended)</option><option value="low">480p (fast test)</option><option value="high">1080p (slow)</option></select></div>
      <div class="field"><label for="camera">Camera movement</label><select id="camera" name="camera"><option value="on">On: slow zoom (cinematic)</option><option value="off">Off: fixed camera</option></select></div>
    </div>
    <div class="actions">
      <button class="btn" type="submit"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>Render video</button>
    </div>
    <p class="hint">Takes 30 seconds to a few minutes on the free server. The next page shows the render working, and you can close the tab, your video will be waiting in Your videos. A video you already rendered comes back at once, no re-render.</p>
  </section>
</form>
<section id="presets" aria-label="Presets">
  <h2>Presets</h2>
  <p class="lead">Every card is the real equation, plotted. Tap one and the form fills with it.</p>
  <ul class="gallery">
    {% for k,v in presets.items() %}<li>
      <a class="card" href="/?preset={{ k }}#render">
        <span class="thumb">{{ thumbs[k] | safe if k in thumbs }}</span>
        <span class="card-body">
          <h3>{{ v.label }}</h3>
          <p>{{ (v.story or v.why or "") | truncate(90, end="…") }}</p>
          <span class="viral">Viral {{ v.viral }} of 5</span>
        </span>
      </a>
    </li>{% endfor %}
  </ul>
</section>
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
<p class="note">Videos are saved in the outputs/ folder too. The video itself is silent. After rendering you get a song suggestion (name and timestamps) to add in Instagram or CapCut. Videos older than an hour are cleaned up automatically, so download any you want to keep.</p>
{% if videos %}<section id="videos" aria-label="Your videos">
  <h2>Your videos</h2>
  <p class="lead">Select one to preview.</p>
  <ul class="rows">{% for v in videos %}<li class="video-row">
    {% if v.poster %}<img class="thumb-sm" src="/poster/{{ v.id }}" alt="">{% else %}<span class="thumb-ph" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="5" width="18" height="14" rx="4"/><path d="M3 9h18"/></svg></span>{% endif %}
    <span class="row-title">{{ v.title }}</span>
    <span class="row-text"><a href="/result/{{ v.id }}">Preview</a> &nbsp; <a href="/download/{{ v.id }}">Download</a></span>
  </li>{% endfor %}</ul>
</section>{% endif %}
<footer class="footer">
  <span>Manim Equation Cinema. Videos are silent, add the suggested song when you post.</span>
  <a href="https://github.com/mobeennasir/manim-equation-cinema">Code on GitHub</a>
</footer>
</div>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>
<script>
(function () {
  if (!window.gsap || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  gsap.from(".hero-text > *", { y: 24, opacity: 0, duration: 0.8, stagger: 0.12, ease: "power3.out" });
  gsap.from(".hero-panel", { y: 32, opacity: 0, duration: 1, delay: 0.25, ease: "power3.out" });
  var cards = document.querySelectorAll(".gallery .card");
  if (!("IntersectionObserver" in window) || !cards.length) return;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) {
        gsap.fromTo(e.target, { y: 24, opacity: 0 }, { y: 0, opacity: 1, duration: 0.6, ease: "power3.out" });
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.15 });
  cards.forEach(function (c) { io.observe(c); });
})();
</script>
</body></html>
"""

WAITING = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rendering your video</title>
<meta name="description" content="Your equation video is rendering. This page takes you to it when it is ready.">
<noscript><meta http-equiv="refresh" content="8"></noscript>
<link href="https://fonts.googleapis.com/css2?family=Funnel+Display:wght@300;400;500&family=Funnel+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>{{ style | safe }}</style></head><body>
<div class="shell">
<div class="waiting">
  <div class="curve">{{ curve_svg | safe }}</div>
  <h1>Your video is rendering</h1>
  <p class="lead">{{ title }}. Manim is drawing it now.</p>
  <p class="stage" id="stage">Writing the equation</p>
  <div class="meter" role="progressbar" aria-label="Rendering progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" id="meter"><span id="bar"></span></div>
  <p class="meta"><span id="clock">0s</span> elapsed. Renders take 30 seconds to a few minutes on the free server. Stages are approximate.</p>
  <p class="meta">You can close this tab. Your video will be in Your videos on the home page when it is ready.</p>
  <div class="err" id="err" role="alert"{% if not error %} hidden{% endif %}>{{ error }} <a href="/">Back to the form</a></div>
  {% if not error %}<p class="meta"><a href="/">Back to the form</a></p>{% endif %}
</div>
</div>
<script>
(function () {
  var job = "{{ job }}";
  var start = Date.now();
  var bar = document.getElementById("bar");
  var meter = document.getElementById("meter");
  var clock = document.getElementById("clock");
  var stage = document.getElementById("stage");
  var stages = ["Writing the equation", "Drawing the curve", "Lighting the scene", "Encoding the video"];
  var si = 0;
  setInterval(function () {
    var s = Math.floor((Date.now() - start) / 1000);
    clock.textContent = s + "s";
    var pct = Math.min(100, Math.round(s / 90 * 100));
    bar.style.width = pct + "%";
    meter.setAttribute("aria-valuenow", String(pct));
  }, 1000);
  setInterval(function () {
    si = (si + 1) % stages.length;
    stage.textContent = stages[si];
  }, 4000);
  function poll() {
    fetch("/status/" + job).then(function (r) { return r.json(); }).then(function (d) {
      if (d.state === "done") { window.location = "/result/" + job; return; }
      if (d.state === "error") {
        var err = document.getElementById("err");
        err.hidden = false;
        err.firstChild.textContent = (d.message || "The render failed.") + " ";
        return;
      }
      setTimeout(poll, 3000);
    }).catch(function () { setTimeout(poll, 3000); });
  }
  {% if not error %}poll();{% endif %}
})();
</script>
</body></html>
"""

RESULT = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Your video</title>
<meta name="description" content="Your rendered equation video, ready to watch and download.">
<link href="https://fonts.googleapis.com/css2?family=Funnel+Display:wght@300;400;500&family=Funnel+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>{{ style | safe }}</style></head><body>
<div class="shell">
<header class="topbar">
  <a class="wordmark" href="/">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="4"/><path d="M3 9h18M7 5l2.5 4M12 5l2.5 4M17 5l2.5 4"/></svg>
    Manim Equation Cinema
  </a>
  <nav class="topnav" aria-label="Sections">
    <a href="/#presets">Presets</a>
    <a href="/#videos">Your videos</a>
  </nav>
</header>
<div class="settle">
  <h1>Your video is ready</h1>
  {% if cached %}<p class="lead">{{ title }}. Served from an earlier render, no waiting.</p>
  {% elif secs %}<p class="lead">{{ title }}, rendered in {{ secs }}s. Watch it here first:</p>
  {% else %}<p class="lead">{{ title }}. Watch it here first:</p>{% endif %}
</div>
{% if story %}<p class="note">{{ story }}</p>{% endif %}
<div class="clear video-panel">
  <video controls muted autoplay loop playsinline preload="auto"{% if poster %} poster="{{ poster }}"{% endif %} src="/watch/{{ job }}"></video>
</div>
<div class="audio">
  <h2>Add this audio when you post</h2>
  <p>The video is silent.</p>
  <p>{{ audio.song }} by {{ audio.artist }} ({{ audio.language }})</p>
  <p>Use {{ audio.start_fmt }} to {{ audio.end_fmt }} (approx.), {{ audio.moment }}</p>
  <p>{{ audio.why }}</p>
  <p class="tip">{{ audio.tip }} Timestamps are approximate. Check the hook in Instagram’s music picker before posting.</p>
</div>
<div class="actions">
  <a class="btn" href="/download/{{ job }}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M12 4v12M6 10l6 6 6-6M5 20h14"/></svg>Download video (.mp4)</a>
  <a class="btn btn--clear" href="/"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>Render another equation</a>
</div>
<p class="note">Clicking Download saves equation-{{ job }}.mp4 to your device (usually your Downloads folder). The same file is also in the project’s outputs/ folder. Use the player above to preview (play, pause, scrub, or fullscreen) before you download. Videos older than an hour are cleaned up automatically.</p>
</div>
</body></html>
"""

def list_outputs():
    """Newest rendered videos first, with display titles and poster flags."""
    try:
        files = [f for f in os.listdir(OUT_DIR) if f.endswith(".mp4")]
    except FileNotFoundError:
        return []
    files.sort(key=lambda f: os.path.getmtime(os.path.join(OUT_DIR, f)), reverse=True)
    out = []
    for f in files[:10]:
        name = f[:-4]
        title = name
        try:
            with open(os.path.join(OUT_DIR, f"{name}.json")) as fh:
                title = json.load(fh).get("title", name)
        except (OSError, ValueError):
            pass
        out.append({"id": name, "title": title,
                    "poster": os.path.exists(os.path.join(OUT_DIR, f"{name}-poster.jpg"))})
    return out


def _page_error(message, code=400):
    return render_template_string(PAGE, style=STYLE, presets=PRESETS, thumbs=THUMBS,
                                  hero_svg=HERO_SVG, selected_preset="", error=message,
                                  videos=list_outputs()), code


@app.route("/", methods=["GET"])
def home():
    selected = request.args.get("preset", "")
    if selected not in PRESETS:
        selected = ""
    return render_template_string(PAGE, style=STYLE, presets=PRESETS, thumbs=THUMBS,
                                  hero_svg=HERO_SVG, selected_preset=selected,
                                  error="", videos=list_outputs())


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
        return _page_error(str(exc), 400)
    cfg["camera_moves"] = form.get("camera", "on") != "off"
    cfg.setdefault("lap_time", None)

    # Semantic cache: this exact request already has a saved video.
    key = cache_key_for(form, preset, cfg)
    if cached_video_path(key):
        poster = f"/poster/{key}" if os.path.exists(os.path.join(OUT_DIR, f"{key}-poster.jpg")) else ""
        _write_status(key, "done", secs=0, cached=True, poster=poster,
                      title=cfg.get("title", key))
        return redirect(url_for("result_page", job=key))
    with _ACTIVE_LOCK:
        if key in _ACTIVE_JOBS:
            return redirect(url_for("waiting", job=key))
        _ACTIVE_JOBS.add(key)

    job_dir = os.path.join(JOBS_DIR, key)
    os.makedirs(job_dir, exist_ok=True)
    cfg_path = os.path.join(job_dir, "equation.json")
    save_config(cfg, cfg_path)
    _write_status(key, "rendering", title=cfg.get("title", "Equation"))
    quality = form.get("quality", "medium")
    threading.Thread(target=_run_job, args=(key, cfg, cfg_path, quality),
                     daemon=True, name=f"render-{key}").start()
    return redirect(url_for("waiting", job=key))


@app.route("/waiting/<job>")
def waiting(job):
    """Loading screen. Redirects to the result once the video is ready."""
    safe = "".join(c for c in job if c.isalnum() or c in "-_")
    status = _read_status(safe)
    if status is None:
        return _page_error("Video not found, render it again.", 404)
    if status.get("state") == "done":
        return redirect(url_for("result_page", job=safe))
    curve = HERO_SVG
    try:
        cfg = load_config(os.path.join(JOBS_DIR, safe, "equation.json"))
        svg = config_svg(cfg, 420, 280, draw="draw-loop")
        if svg:
            curve = svg
    except Exception:
        pass
    if status.get("state") == "error":
        return render_template_string(WAITING, style=STYLE, job=safe,
                                      title=status.get("title", "Equation"),
                                      curve_svg=curve,
                                      error=status.get("message", "The render failed."))
    return render_template_string(WAITING, style=STYLE, job=safe,
                                  title=status.get("title", "Equation"),
                                  curve_svg=curve, error="")


@app.route("/status/<job>")
def status(job):
    """JSON job state for the loading page's poll."""
    safe = "".join(c for c in job if c.isalnum() or c in "-_")
    return jsonify(_read_status(safe) or {"state": "unknown"})


@app.route("/result/<job>")
def result_page(job):
    """Result page: the finished video, the audio suggestion, the download."""
    safe = "".join(c for c in job if c.isalnum() or c in "-_")
    if not os.path.exists(os.path.join(OUT_DIR, f"{safe}.mp4")):
        status = _read_status(safe)
        if status and status.get("state") in ("rendering", "error"):
            return redirect(url_for("waiting", job=safe))
        return "Video not found, render it again.", 404
    status = _read_status(safe) or {}
    title, story = safe, ""
    audio = audio_for({"audio": "calm"})
    secs = int(status.get("secs", 0) or 0)
    cached = bool(status.get("cached"))
    try:
        cfg = load_config(os.path.join(JOBS_DIR, safe, "equation.json"))
        title = cfg.get("title", title)
        story = cfg.get("story", "")
        audio = audio_for(cfg)
    except Exception:
        try:
            with open(os.path.join(OUT_DIR, f"{safe}.json")) as fh:
                title = json.load(fh).get("title", title)
        except (OSError, ValueError):
            pass
    audio = {**audio, "start_fmt": fmt_time(audio["start"]), "end_fmt": fmt_time(audio["end"])}
    poster = status.get("poster") or (
        f"/poster/{safe}" if os.path.exists(os.path.join(OUT_DIR, f"{safe}-poster.jpg")) else "")
    return render_template_string(RESULT, style=STYLE, job=safe, title=title, story=story,
                                  secs=secs, cached=cached, audio=audio, poster=poster)


@app.route("/watch/<job>")
def watch(job):
    """Stream the video for the in-browser preview player (no download)."""
    safe = "".join(c for c in job if c.isalnum() or c in "-_")
    path = os.path.join(OUT_DIR, f"{safe}.mp4")
    if not os.path.exists(path):
        return "Video not found, render it again.", 404
    return send_file(path, as_attachment=False, mimetype="video/mp4")


@app.route("/poster/<job>")
def poster(job):
    """Still frame for the result page's video poster."""
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
        return "Video not found, render it again.", 404
    return send_file(path, as_attachment=True, download_name=f"equation-{safe}.mp4")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"Open http://127.0.0.1:{port} in your browser")
    app.run(host="0.0.0.0", port=port, threaded=True)

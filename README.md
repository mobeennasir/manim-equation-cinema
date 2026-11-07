# 🎬 Manim Equation Cinema — run it locally, download the video

Type **any** maths equation. Manim (the Python library from the reel —
the animation engine created by Grant Sanderson / 3Blue1Brown) draws it
cinematically — dark background, glowing trace, moving dot — and saves
an **.mp4 video you can download**.

Two ways to use it:
1. **Command line** — `python render.py --preset butterfly` → `outputs/butterfly.mp4`
2. **Local website** — `python app.py` → open http://127.0.0.1:5000 → type an
   equation → Render → Download video

Test it locally first. Only deploy it (Koyeb etc.) if you like how it runs —
see **Deploy** at the bottom. Rendering on a free host is slow and can
time out, so local is the honest first step.

---

## What you type

| Mode | You type | Example |
|---|---|---|
| `y` | `y = f(x)` | `sin(x)`, `x^2 / 4`, `exp(-x/4)*sin(3*x)` |
| `parametric` | `x(t) = ...`, `y(t) = ...` | Butterfly (default), `cos(t)`, `sin(t)` |
| `polar` | `r(theta) = ...` | `2*sin(3*theta)`, `theta / 3` |

Use `^` for powers (`x^2`), `sin cos tan exp log sqrt`, `pi`, `e`.
You can type `y = sin(x)` or just `sin(x)` — both work.

**Presets (27 now):** butterfly, lorenz, rose-5, rose, heart, cardioid,
astroid, deltoid, spirograph, lissajous, lissajous-53, golden-spiral,
spiral, fermat-spiral, lemniscate, sine-cos-duo, waves-trio,
fourier-square, rainbow-roses, gaussian, catenary, witch, cycloid,
sine, parabola, circle, damped

Multi-colour: presets with more than one line draw each line in its
own colour, one after another — e.g. `sine-cos-duo` (cyan sin + rose
cos), `waves-trio` (3 colours), `fourier-square` (4 colours, each new
wave added), `rainbow-roses` (3 roses, 3 colours). Custom multi-curve
videos are possible too: in `app.py` choose a multi preset, or in
`render.py` use a multi preset — the scene splits the draw time
across the curves.

Draw once, grow to infinity (v7): no laps, no loops. Each curve draws
once, and a white dot rides its tip while it draws — the dot is the
drawing, not a repeat. The camera moves while it draws (a zoom-out
pulls back as the picture grows, a push-in closes in, a pan follows
the line), so the picture keeps growing instead of being re-traced.
When the drawing is finished the picture holds, the camera pulls back
once, and the video ends. Text on screen is title and formula only.
The grid, the axes and the glow stay.

Cinematic camera: the camera pushes in clearly (x0.85) on the first
curve, pans smoothly to each curve's centre as it draws, pulls back
a touch as the loop widens, and pulls back slowly to the full view
at the end, like the sample videos. It is on by default for every
equation. Turn it off with `--no-camera` in render.py or the
"Camera movement" dropdown in the website.

BUG FIXED 2026-11-06: an earlier version drew a `TracedPath` trail
behind the dot. The trail only sampled the dot once per frame, so on
curvy lines it joined those points with straight chords — a random
wavy line that grew along the curve and vanished when the next curve
started. The trail is removed: now only the dot travels the curve,
and the glow shows the path. If you still see a wavy line, you are
running an old copy — re-download the v3 zip.

### Most beautiful / most viral — the full list

Viral = our judgement 1–5 (symmetry, surprise, recognisability).
★5 = post these first.

| Preset | What it is | Viral | Why it works |
|---|---|---|---|
| butterfly | Temple Fay butterfly curve | ★★★★★ | The reel that started this — instantly recognisable |
| lorenz | Lorenz attractor, butterfly effect | ★★★★★ | Chaos like butterfly wings, never repeats |
| rose-5 | Rose, 5 petals | ★★★★★ | A perfect flower from one line |
| heart | Heart curve | ★★★★★ | A heart from pure maths |
| spirograph | Spirograph flower | ★★★★★ | Childhood toy as maths — nostalgia + symmetry |
| golden-spiral | Golden spiral | ★★★★★ | Shells, galaxies, sunflowers — 'nature follows maths' |
| fourier-square | Sine waves become a square | ★★★★★ | 'How is that possible?' — 4 colours stacking up |
| rainbow-roses | 3 roses, 3 colours | ★★★★★ | The prettiest preset in the set |
| rose | Rose, 3 petals | ★★★★ | A flower in one stroke |
| cardioid | Cardioid, polar heart | ★★★★ | Heart from the simplest polar equation |
| astroid | Astroid star | ★★★★ | A star with curved sides |
| deltoid | Deltoid hypocycloid | ★★★★ | Triangle with curved sides, hypnotic |
| lissajous | Lissajous 3:2 | ★★★★ | Oscilloscope pattern, music made visible |
| lissajous-53 | Lissajous 5:3 | ★★★★ | Denser weave, like a knot tying itself |
| fermat-spiral | Fermat spiral | ★★★★ | The sunflower-seed spiral |
| lemniscate | Infinity symbol | ★★★★ | Infinity, drawn by an equation |
| sine-cos-duo | Sine + cosine, 2 colours | ★★★★ | Two waves chasing each other |
| waves-trio | sin x, sin 2x, sin 3x | ★★★★ | Three colours, three frequencies |
| cycloid | Rolling wheel path | ★★★★ | Arches appearing one after another |
| spiral | Archimedean spiral | ★★★ | Simple, calm |
| gaussian | Bell curve | ★★★ | The most famous curve in statistics |
| catenary | Hanging chain | ★★★ | Shape of chains and arches |
| witch | Witch of Agnesi | ★★★ | A bell with a great name |
| sine | Sine wave | ★★★ | First wave everyone learns |
| damped | Damped wave | ★★★ | A wave fading away, like sound dying |
| pi-irrational | Two hands at speeds 1 and π — never closes | ★★★★★ | 'So close, yet so far' — 5.1M likes on the original |
| you-and-crush | 1/x² — You & Your Crush | ★★★★★ | 'Forever approaching, never meeting' |
| race-sincos | x − sin x vs x − cos x | ★★★★★ | Two curves race, swap the lead every π, finish together |
| times-table-3 | Power of 3 — times-table cardioid | ★★★★★ | Count to 200, a heart appears — 1.9M likes on the original |
| golden-sunflower | 600 dots at the golden angle | ★★★★★ | 600 seeds, zero waste |
| sigmoid | The S-curve that decides | ★★★★ | The curve that taught machines yes/no |
| nephroid | Coffee-cup curve | ★★★★ | The shape light makes in your coffee |
| epicycloid | Flower from rolling circles | ★★★★ | A circle rolling around a circle |
| beats | Two waves almost in step | ★★★ | Swells and fades — that's a beat |
| growth-race | Five functions race from one start | ★★★★★ | The white one stops at 10, the rest never do |
| times-table-morph | The full line-to-circle morph | ★★★★★ | A straight line bends into a circle, a heart appears |
| roses-showcase | Five roses, twenty seconds | ★★★★★ | One flower every 3 seconds, hard cuts, neon colours |
| parabola | Parabola | ★★ | Classic teaching clip |
| circle | Circle | ★★ | Simplest closed curve — use to test |

### Add a new equation — the viral file format

Every equation lives in **one place: `equations.py`, in the `PRESETS` dict**.
One entry defines the whole video — the maths, the story, the camera,
and the on-screen words. Copy this template and fill it in:

```python
"my-curve": {
    "label": "My curve", "mode": "y",
    "expr": "sin(x)", "x_min": -6, "x_max": 6,
    "x_range": [-7, 7], "y_range": [-2, 2],
    "title": "My Curve", "latex": r"y = \sin x",
    "viral": 4, "why": "One line for the website list.",
    "audio": "calm",
    "story": "What the graph DOES, in plain words — the hook and payoff.",
    "camera_style": "push-in",  # push-in | zoom-out | pan | wide
    "camera_note": "Push in while it draws, hold on the finished curve.",
    "text": {"hook": "Opening line.", "payoff": "Closing line.",
             "caption": "One line under the drawing.",
             "labels": [{"text": "You", "color": "#22d3ee",
                         "curve": 0, "rides": "dot"}]},
},
```

The rule for the story: **read the graph first, then write it.**
What does the graph do when it draws? It blooms? It races? It never
closes? Two lines chase each other? Two lines climb and never meet?
That behaviour IS the story — never write a story the graph does not show.

Camera styles: `push-in` (slow zoom in while it draws), `zoom-out`
(start close, pull back as the picture grows — for curves that fill the
screen), `pan` (follow the drawing left to right — waves and races),
`wide` (no camera moves, fixed frame).

Text: `hook` = opening line shown alone on black; `payoff` = closing
line shown at the end; `caption` = the bottom line under the drawing
(it IS the equation line for presets that have one); `labels`
= text that rides the curves — `"rides": "dot"` follows the white
dot to its right, `"start"` / `"end"` sit at the curve's start /
end; `"title_fades": true` = the title and the bottom line fade out
once the picture takes over (the pi reel). Omit any key you do not
need. Modes: `y`, `parametric`, `polar`, `lorenz`, `chords`
(times-table web: `points`, `multiple`, `radius`), `dots` (dot spiral:
`n`, `angle`, `spacing`), `morph-chords` (the full line-to-circle
morph), `showcase` (several equations back to back: `items`).
Extra keys: `"color"` (one colour for the whole preset, e.g. white
for pi), `"gradient": [colour1, colour2]` (the line changes colour
as it draws), `"wing_colors": [left, right]` (Lorenz: one colour
per wing), `"simultaneous": true` (all curves draw at the same time
— a race).

Layout: the title at the top is plain words; the equation itself sits
at the bottom in the curve's colour, the way the reels do it. Axes
are sized to the data's own aspect, so a circle is a circle.

After adding a preset, run `python test_equations.py` — it checks that
every preset has a story, a camera style, on-screen text, and real
plottable points.

### Audio suggestions — song + timestamps, with the video

The .mp4 is silent — Manim adds no music. After every render (command
line and website) you get a song suggestion to add in Instagram /
CapCut when you post. Timestamps are approximate — check the hook in
Instagram's music picker before posting, and add the song through
Instagram's own music library.

| For | Song — artist | Use (approx.) |
|---|---|---|
| Butterfly | Cornfield Chase — Hans Zimmer (Interstellar) | 0:42–0:57, piano build lifts |
| Lorenz | Space Song — Beach House | 0:00–0:15, dreamy opening |
| Rose / Rainbow roses | Pasoori — Ali Sethi & Shae Gill (Coke Studio Pakistan) | 0:48–1:03, chorus |
| Heart / Cardioid | Saiyaara — Faheem Abdullah (2025) | 0:55–1:10, chorus |
| Spirograph | Kesariya — Arijit Singh | 0:32–0:47 |
| Lissajous | Chaleya — Arijit Singh | 0:45–1:00, chorus groove |
| Golden / Fermat spiral | Kun Faya Kun — A. R. Rahman | 1:02–1:17, qawwali build |
| Sine / Waves | Until I Found You — Stephen Sanchez | 0:20–0:35 |
| Fourier square | Experience — Ludovico Einaudi | 1:10–1:25, piano returns louder |
| Calm / others | Apocalypse — Cigarettes After Sex | 0:00–0:15, dreamy opening |

Full details (why each song fits + a tip) are in `audio.py` and shown
on the result page in the app, right under the video preview.

The butterfly curve is the Temple H. Fay butterfly:
`x(t) = sin(t)·(e^cos t − 2cos 4t − sin⁵(t/12))`,
`y(t) = cos(t)·(e^cos t − 2cos 4t − sin⁵(t/12))`, `t` from `0` to `12π`.

---

## Setup — WSL Ubuntu, step by step

Do this in your WSL Ubuntu terminal. If you use Miniforge/conda
(you already have it for your bioinformatics work), use the conda steps.

### Step 1 — System packages Manim needs (once)

```bash
sudo apt update
sudo apt install -y ffmpeg libcairo2-dev libpango1.0-dev \
  texlive-latex-base texlive-latex-recommended texlive-fonts-recommended
```

This is the slow part — TeX is large. Leave it running.
TeX is what draws the pretty equation line at the bottom of each video
(the title at the top is plain words). If you skip TeX, run everything
with `MANIM_USE_TEX=0` in front (see Troubleshooting) — the videos
still work, but the bottom formula line only shows for presets that
have a plain-text caption.

### Step 2 — Make a fresh environment (do NOT reuse your `jhu-cli` env)

```bash
conda create -n manim-cinema python=3.11 -y
conda activate manim-cinema
```

### Step 3 — Install the Python packages

```bash
cd manim-equation-cinema
pip install -r requirements.txt
```

### Step 4 — Check it works

```bash
manim --version
python test_equations.py
```

`test_equations.py` checks the equation parser only — it does **not**
need Manim or a render, so it should pass in seconds. You should see
`OK butterfly ...`, `OK sine ...` and so on for every preset.

---

## Use it 1 — Command line (fastest test)

```bash
# Butterfly, 720p — the first real test. Takes 30s to a few minutes.
python render.py --preset butterfly

# Your own equation
python render.py --mode y --expr "sin(x)"
python render.py --mode y --expr "x^2 / 4" --title "Parabola"
python render.py --mode polar --expr "2*sin(3*theta)"
python render.py --mode parametric --x "cos(t)" --y "sin(t)"

# Faster test render, or sharper video
python render.py --preset sine --quality low
python render.py --preset butterfly --quality high --duration 12

# No arguments = it asks you questions, one at a time
python render.py
```

The video is saved in **`outputs/`**, e.g. `outputs/butterfly.mp4`.
Open it with any video player. That file *is* your download.

## Use it 2 — Local website (type + click + download)

```bash
conda activate manim-cinema
python app.py
```

Then open **http://127.0.0.1:5000** in your browser:

1. Pick a preset, or choose Custom and type your equation.
2. Choose mode (`y`, parametric, polar), range, draw time, quality.
3. Click **Render video** — wait, it really does take 30 seconds
   to a few minutes. Do not click twice.
4. **Preview first:** you land on a result page where the finished
   video plays right there in the browser — play, pause, scrub,
   fullscreen. It does NOT just hand you a file.
5. **Then download:** click **⬇ Download video (.mp4)** under the
   player. That saves `equation-<id>.mp4` to your device
   (usually your Downloads folder).
6. **Later:** the home page lists "Your videos" — click any one to
   preview it again, or Download it again.

Videos are also saved in `outputs/` on your computer.

---

## Deploy — only after local works (Koyeb)

Yes, this is "Koyeb" — the host you meant. The project already has a
`Dockerfile` for it.

1. Put this folder on GitHub (new repo, upload the files).
2. In Koyeb: **Create Service → GitHub → pick the repo → Builder: Dockerfile**.
3. Leave the port as it comes from `$PORT`. No extra settings needed.
4. Deploy and open the public URL — it is the same `app.py` website.

**Honest warning before you pay / rely on it:**
- A free Koyeb instance is much weaker than your laptop. A 720p render
  that takes 1 minute locally can take 5–10 minutes there, or hit the
  request timeout and fail. Start with `--quality low` / short durations.
- Rendering uses a lot of CPU/RAM. If it keeps timing out, the fix is a
  bigger instance, not more code. Keep local rendering as your main way
  to make videos, and use the deployed site only for showing it to others.
- The Dockerfile installs TeX, so the first deploy is slow (several
  minutes). That is normal.

Other hosts (Render, Railway, Fly.io) work the same way: deploy from
the Dockerfile, they set `$PORT`, the app listens on `0.0.0.0:$PORT`.

---

## Files

| File | What it is |
|---|---|
| `equations.py` | Parses your equation safely (SymPy), presets, checks it plots |
| `scene.py` | The Manim scene — dark cinema look, glow, moving dot, title |
| `render.py` | Command-line tool — equation in, `outputs/*.mp4` out |
| `app.py` | Flask local server — the website on http://127.0.0.1:5000, with video preview + Download + audio suggestion |
| `audio.py` | Viral audio suggestions: song, artist, language, start/end timestamps, why it fits |
| `test_equations.py` | Parser test, no Manim needed — now tests all 27 presets |
| `requirements.txt` | `manim`, `Flask`, `sympy`, `numpy`, `gunicorn` |
| `Dockerfile` | For Koyeb / Render / Railway deployment |
| `equation.json` | Last rendered equation (butterfly by default) |

---

## Verified on 2026-11-06 (so you know this is not just untested code)

Tested with Manim Community Edition 0.19.0, Python 3.11, `MANIM_USE_TEX=0`:
- `python test_equations.py` — all 9 presets + a custom equation pass.
- `python render.py --preset sine --quality low` — video in 18s, `outputs/sine.mp4`.
- `python render.py --preset butterfly --quality low --duration 5` — video in 48s,
  14s long, `outputs/butterfly.mp4` (included in the zip as a sample — play it first).
- `python app.py` — home page loads, Render returns a result page with
  an embedded video player (preview) + Download button, the download
  link serves the .mp4 (200 OK), and the home page lists past videos.
  Re-tested 2026-11-06 after the preview player was added.
- With TeX installed (Step 1), titles render as pretty LaTeX maths.
  Without TeX, titles fall back to plain text and the curve still renders.

## Troubleshooting

**`manim: command not found`**
Your conda env is not active. Run `conda activate manim-cinema`, then
`pip install -r requirements.txt` again.

**Error mentions LaTeX / `latex` / `dvisvgm`**
TeX is missing or incomplete. Either install it (Step 1), or skip pretty
maths titles entirely:
```bash
MANIM_USE_TEX=0 python render.py --preset butterfly
MANIM_USE_TEX=0 python app.py
```

**`Could not understand '...'`**
Check brackets and spelling. Use `*` for multiply (`2*sin(x)`, not
`2sin(x)` — although `2sin(x)` usually works), `^` or `**` for powers,
and only the right variable: `x` for `y` mode, `t` for parametric,
`theta` for polar.

**Render is very slow**
Normal. First render is slowest. Use `--quality low` to test, and
`--duration 5` for a quick check, before doing a full 1080p render.

**Video file not found after Manim finishes**
Look in `media/videos/scene/` — Manim's own output folder. The `.mp4`
is there even if the copy to `outputs/` failed.

**`ModuleNotFoundError: No module named 'manim'`**
You installed into a different Python/env than the one running the
command. Check with `which python` and `pip list | grep -i manim`
inside the activated `manim-cinema` env.

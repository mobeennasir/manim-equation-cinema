"""
render.py — command line: type any equation, get a Manim video (mp4).

Examples
--------
    python render.py --preset butterfly
    python render.py --preset sine
    python render.py --mode y --expr "sin(x)" --xmin -6.28 --xmax 6.28
    python render.py --mode y --expr "x^2 / 4" --title "Parabola"
    python render.py --mode polar --expr "2*sin(3*theta)"
    python render.py --mode parametric --x "cos(t)" --y "sin(t)"
    python render.py --preset butterfly --quality high --duration 12

With no arguments it asks you questions, one at a time.

Output:  outputs/<name>.mp4   (and equation.json is saved for the scene)
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

from audio import audio_line
from equations import (
    PRESETS,
    config_from_preset,
    latex_of,
    save_config,
    validate_config,
)

BASE = os.path.dirname(os.path.abspath(__file__))
QUALITY_FLAGS = {"low": "-ql", "medium": "-qm", "high": "-qh"}
QUALITY_DIR = {"low": "480p15", "medium": "720p30", "high": "1080p60"}


def ask(prompt, default=""):
    answer = input(f"{prompt} [{default}]: " if default else f"{prompt}: ").strip()
    return answer or default


def interactive_config():
    print("\n--- Manim Equation Cinema ---\nPresets:", ", ".join(PRESETS))
    preset = ask("Preset (or press Enter for butterfly)", "butterfly")
    if preset in PRESETS:
        return config_from_preset(preset)
    print("No preset — build your own.")
    mode = ask("Mode: y / parametric / polar", "y")
    cfg = {"mode": mode, "color": "#22d3ee", "duration": 8.0,
           "x_range": [-7, 7], "y_range": [-3, 3], "title": "My Equation"}
    if mode == "y":
        cfg["expr"] = ask("y = ", "sin(x)")
        cfg["x_min"] = float(ask("x from", "-6.28"))
        cfg["x_max"] = float(ask("x to", "6.28"))
        cfg["latex"] = "y = " + latex_of(cfg["expr"], "x")
        cfg["title"] = "y = " + cfg["expr"]
    elif mode == "parametric":
        cfg["x_expr"] = ask("x(t) = ", "cos(t)")
        cfg["y_expr"] = ask("y(t) = ", "sin(t)")
        cfg["t_min"] = 0.0
        cfg["t_max"] = float(ask("t to (2*pi = 6.28)", "6.28"))
        cfg["x_range"] = [-2, 2]
        cfg["y_range"] = [-2, 2]
        cfg["latex"] = "x(t)=" + latex_of(cfg["x_expr"], "t") + r",\; y(t)=" + latex_of(cfg["y_expr"], "t")
    elif mode == "polar":
        cfg["expr"] = ask("r(theta) = ", "2*sin(3*theta)")
        cfg["t_min"] = 0.0
        cfg["t_max"] = float(ask("theta to", "6.28"))
        cfg["x_range"] = [-3, 3]
        cfg["y_range"] = [-3, 3]
        cfg["latex"] = "r = " + latex_of(cfg["expr"], "theta")
    else:
        raise SystemExit(f"Unknown mode '{mode}'. Use y, parametric or polar.")
    return cfg


def main():
    parser = argparse.ArgumentParser(description="Render any equation as a Manim video.")
    parser.add_argument("--preset", choices=list(PRESETS), help="Use a preset curve")
    parser.add_argument("--mode", choices=["y", "parametric", "polar"])
    parser.add_argument("--expr", help="y=f(x) or r(theta) expression, e.g. 'sin(x)'")
    parser.add_argument("--x", dest="x_expr", help="Parametric x(t) expression")
    parser.add_argument("--y", dest="y_expr", help="Parametric y(t) expression")
    parser.add_argument("--xmin", type=float, default=-6.28)
    parser.add_argument("--xmax", type=float, default=6.28)
    parser.add_argument("--tmax", type=float, default=6.28, help="t / theta upper end")
    parser.add_argument("--title", default="")
    parser.add_argument("--color", default="#22d3ee", help="Curve colour, e.g. #f59e0b")
    parser.add_argument("--duration", type=float, default=None, help="Draw time in seconds")
    parser.add_argument("--no-camera", action="store_true", help="Turn off the cinematic camera zoom")
    parser.add_argument("--quality", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--name", default="", help="Output file name (without .mp4)")
    args = parser.parse_args()

    if args.preset:
        cfg = config_from_preset(args.preset)
    elif args.mode:
        cfg = {"mode": args.mode, "color": args.color,
               "duration": args.duration or 8.0,
               "x_range": [-7, 7], "y_range": [-3, 3]}
        if args.mode == "y":
            if not args.expr:
                parser.error("--expr is required for mode y, e.g. --expr 'sin(x)'")
            cfg.update(expr=args.expr, x_min=args.xmin, x_max=args.xmax,
                       title=args.title or f"y = {args.expr}",
                       latex="y = " + latex_of(args.expr, "x"))
        elif args.mode == "parametric":
            if not args.x_expr or not args.y_expr:
                parser.error("parametric needs --x and --y, e.g. --x 'cos(t)' --y 'sin(t)'")
            cfg.update(x_expr=args.x_expr, y_expr=args.y_expr, t_min=0.0, t_max=args.tmax,
                       x_range=[-2, 2], y_range=[-2, 2],
                       title=args.title or "Parametric Curve",
                       latex="x(t)=" + latex_of(args.x_expr, "t") + r",\; y(t)=" + latex_of(args.y_expr, "t"))
        else:  # polar
            if not args.expr:
                parser.error("--expr is required for polar, e.g. --expr '2*sin(3*theta)'")
            cfg.update(expr=args.expr, t_min=0.0, t_max=args.tmax,
                       x_range=[-3, 3], y_range=[-3, 3],
                       title=args.title or f"r = {args.expr}",
                       latex="r = " + latex_of(args.expr, "theta"))
    else:
        cfg = interactive_config()

    if args.duration:
        cfg["duration"] = args.duration
    cfg["camera_moves"] = not args.no_camera
    cfg.setdefault("lap_time", 2.5)
    if args.title:
        cfg["title"] = args.title
    if args.color != "#22d3ee":
        cfg["color"] = args.color

    # --- 1. check the equation really plots, before waiting for Manim
    try:
        info = validate_config(cfg)
    except ValueError as exc:
        print(f"\nERROR: {exc}\nFix the equation and try again.")
        raise SystemExit(1) from exc
    print(f"\nEquation OK — {info['finite_points']} plottable points, "
          f"x in [{info['x_min']:.2f}, {info['x_max']:.2f}], "
          f"y in [{info['y_min']:.2f}, {info['y_max']:.2f}]")

    # --- 2. save it where scene.py will read it
    cfg_path = os.path.join(BASE, "equation.json")
    save_config(cfg, cfg_path)

    name = args.name or cfg.get("preset") or "equation"
    name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    out_dir = os.path.join(BASE, "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{name}.mp4")

    # --- 3. run Manim
    env = dict(os.environ, EQ_CONFIG=cfg_path)
    cmd = [sys.executable, "-m", "manim", "render",
           QUALITY_FLAGS[args.quality], "--format=mp4",
           "-o", name, "scene.py", "EquationCinema"]
    print("Running:", " ".join(cmd), "\nThis takes 30 seconds to a few minutes — please wait...")
    started = time.time()
    result = subprocess.run(cmd, cwd=BASE, env=env)
    if result.returncode != 0:
        print("\nManim failed. Common fixes are in README.md > Troubleshooting.")
        print("Tip: if the error mentions LaTeX, run with  MANIM_USE_TEX=0  python render.py ...")
        raise SystemExit(result.returncode)

    made = os.path.join(BASE, "media", "videos", "scene",
                        QUALITY_DIR[args.quality], f"{name}.mp4")
    if os.path.exists(made):
        shutil.copyfile(made, out_path)
    elif os.path.exists(out_path):
        pass
    else:
        print(f"\nManim finished but I could not find the video at {made}")
        print("Look in media/videos/scene/ for the .mp4 file.")
        raise SystemExit(1)

    print(f"\nDone in {time.time() - started:.0f}s")
    print(f"Video saved: {out_path}")
    print(audio_line(cfg))
    print("Add that song in Instagram / CapCut when you post — the mp4 itself is silent.")


if __name__ == "__main__":
    main()

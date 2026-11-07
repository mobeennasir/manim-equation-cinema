"""
scene.py — the Manim scene that draws your equation cinematically.

Run it through render.py (recommended) or directly:
    manim render -qm --format=mp4 -o butterfly scene.py EquationCinema

The equation comes from equation.json (or the EQ_CONFIG env var).
Set MANIM_USE_TEX=0 if LaTeX is not installed — titles then use plain
text, and the bottom formula line is skipped unless the preset has a
caption (captions are plain text, so they always show).

Everything about a video is defined in equations.py, in ONE place per
preset: the maths, "story", "camera_style" + "camera_note", and "text"
(hook / payoff / caption / labels that ride the curves). The scene
reads them from the config and plays them — add a new equation there
and it just works.

Layout (the way the reels do it): the TITLE is plain words at the top;
the EQUATION itself sits at the bottom, in the curve's colour. A
preset's "caption" is its bottom line; otherwise the LaTeX formula
is used (needs LaTeX). Custom equations have no bottom line — their
title already is the equation.

Multi-colour: if the config has several curves, each is drawn in its
own colour, one after another, each with its own glowing dot. With
"simultaneous": true they all draw at the same time (a race).

Draw once, grow to infinity (v7): no laps, no loops. The curve draws
once, and a white dot rides its tip while it draws — the dot is the
drawing, not a repeat. The camera moves while it draws (a zoom-out
pulls back as the picture grows, a push-in closes in, a pan follows
the line), so the picture keeps growing instead of being re-traced.
When the drawing is finished the picture holds, the camera pulls back
once, and the video ends. Chords and dots modes have no single path
for a dot, so they bloom on their own — the web / the spiral blooming
IS the animation.

Colour along the drawing: a curve with "gradient" changes colour as
it draws (butterfly: pink -> blue); a Lorenz curve with "wing_colors"
is one colour per wing. Both are built as short segments; the dot
still follows the original single path (never added to the scene).

Camera styles (from the preset's "camera_style"):
  push-in  — a clear push-in on the first curve, then a smooth pan to
             each curve's centre as it draws (the v5 default).
  zoom-out — start close, pull back a little with every curve, so a
             picture that fills the screen is revealed gradually.
  pan      — follow the drawing left to right (waves, races).
  wide     — no camera moves at all, fixed frame.

Special modes: "morph-chords" bends a number line into a circle and
then blooms the chords (the full Power of 3 morph); "showcase" cuts
between several equations, 3 s each, on a faint polar grid.

Text: title and formula only. The title is plain words at the top;
the equation itself sits at the bottom, in the curve's colour. A
preset's "caption" is its bottom line; otherwise the LaTeX formula
is used (needs LaTeX). Custom equations have no bottom line — their
title already is the equation. The preset file still records the
story (hook / payoff / labels) as the record of what the graph does,
but the video shows title and formula only. With "title_fades": true
the title and the formula line fade out once the picture takes over.

Axes: the axes lengths are sized to the data aspect, so a circle is
a circle — the frame is 14.22 x 8 scene units, the axes use at most
12 x 6.8.
"""

import os

import numpy as np
from manim import (
    Axes,
    Circle,
    Create,
    Dot,
    FadeIn,
    FadeOut,
    LaggedStart,
    Line,
    MathTex,
    MoveAlongPath,
    MovingCameraScene,
    NumberPlane,
    Restore,
    Text,
    Transform,
    UP,
    DOWN,
    VGroup,
    VMobject,
    Write,
    config,
)

from equations import (
    curves_from_config,
    load_config,
    lorenz_points,
    make_function,
)

USE_TEX = os.environ.get("MANIM_USE_TEX", "1") != "0"

# Gradient stops for the chords / dots modes: cyan -> rose -> gold,
# the same progression as the times-table reel (blue -> pink -> gold).
_GRADIENT = ("#22d3ee", "#fb7185", "#f59e0b")


def _lerp_hex(c1, c2, t):
    """Linear interpolation between two hex colours."""
    a = np.array([int(c1[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
    b = np.array([int(c2[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
    v = (a + (b - a) * t).astype(int)
    return "#%02x%02x%02x" % tuple(v)


def _gradient_color(t):
    """Colour at position t in 0..1 across the three gradient stops."""
    t = min(1.0, max(0.0, float(t)))
    if t < 0.5:
        return _lerp_hex(_GRADIENT[0], _GRADIENT[1], t * 2)
    return _lerp_hex(_GRADIENT[1], _GRADIENT[2], (t - 0.5) * 2)


def _axes_lengths(x_range, y_range):
    """Scene-unit axes lengths that keep the data aspect true, so a
    circle is a circle. The frame is 14.22 x 8; the axes use at most
    12 wide x 6.8 tall."""
    w = float(x_range[1] - x_range[0])
    h = float(y_range[1] - y_range[0])
    aspect = w / max(h, 1e-9)
    if aspect >= 12 / 6.8:
        return 12.0, 12.0 / aspect
    return 6.8 * aspect, 6.8


def _title_mobject(cfg):
    """Plain-words title at the top — the formula lives at the bottom."""
    return Text(cfg.get("title", "Equation"), font_size=32).to_edge(UP, buff=0.9)


def _formula_mobject(cfg, color):
    """The equation itself, at the bottom, in the curve's colour.
    A preset's caption IS its bottom line; otherwise the LaTeX formula
    (needs LaTeX — without it, no bottom line). Custom equations have
    no bottom line: their title already is the equation."""
    text = cfg.get("text") or {}
    if text.get("caption"):
        return Text(text["caption"], font_size=24, color=color).to_edge(DOWN, buff=0.35)
    if not cfg.get("preset"):
        return None
    latex = cfg.get("latex") or ""
    if USE_TEX and latex:
        try:
            mob = MathTex(latex).scale(0.6)
            if mob.width > 11:
                mob.scale(11 / mob.width)
            return mob.set_color(color).to_edge(DOWN, buff=0.35)
        except Exception:
            pass
    return None


def _segments_from_mob(mob, color_fn, n_seg=600):
    """Split one curve into short line segments, coloured by color_fn.
    color_fn(t, midpoint) -> hex colour, t in 0..1 along the curve.
    The segments are what you SEE; the original mob is what the dot
    follows (it is never added to the scene)."""
    pts = mob.get_points()
    if len(pts) < 2:
        return VGroup()
    count = min(n_seg, len(pts) - 1)
    idx = np.linspace(0, len(pts) - 1, count + 1).astype(int)
    segs = []
    for j in range(len(idx) - 1):
        a, b = pts[idx[j]], pts[idx[j + 1]]
        if np.allclose(a, b):
            continue
        seg = Line(a, b)
        seg.set_color(color_fn(j / max(1, len(idx) - 2), (a + b) / 2))
        seg.set_stroke(width=4)
        segs.append(seg)
    return VGroup(*segs)


def _circle_chords(n, k, r):
    """Times-table chords on a circle of radius r, in scene coords,
    gradient-coloured — used by the morph (there are no axes there)."""
    angs = 2 * np.pi * np.arange(n) / n
    pts = [np.array([r * float(np.cos(a)), r * float(np.sin(a)), 0]) for a in angs]
    lines = []
    for i in range(n):
        line = Line(pts[i], pts[(i * k) % n])
        line.set_color(_gradient_color(i / max(1, n - 1)))
        line.set_stroke(width=2)
        lines.append(line)
    return VGroup(*lines)


def _mob_start(mob):
    """First point of a curve — VGroups (chords / dots / segments)
    hold no points of their own, so read the first submobject."""
    if isinstance(mob, VGroup):
        return mob[0].get_start()
    return mob.get_start()


def _mob_end(mob):
    """Last point of a curve — same VGroup rule as _mob_start."""
    if isinstance(mob, VGroup):
        return mob[-1].get_end()
    return mob.get_end()


def _build_curve(axes, curve):
    """Build one curve. Returns (visible_mob, lap_path): visible_mob
    is what is drawn; lap_path is the single path the dot follows
    (None when there is no single path — chords, dots)."""
    mode = curve["mode"]
    if mode == "y":
        _, f = make_function(curve["expr"], "x")

        def func(x):
            return np.asarray(f(x), dtype=float)

        mob = axes.plot(func, x_range=[curve.get("x_min", -6), curve.get("x_max", 6), 0.01])
    elif mode == "parametric":
        _, fx = make_function(curve["x_expr"], "t")
        _, fy = make_function(curve["y_expr"], "t")

        def param(t):
            return np.array([float(fx(t)), float(fy(t)), 0])

        mob = axes.plot_parametric_curve(
            param, t_range=np.array([curve.get("t_min", 0), curve.get("t_max", 6.28), 0.01]))
    elif mode == "polar":
        _, fr = make_function(curve["expr"], "theta")

        def polar(t):
            r = float(fr(t))
            return np.array([r * np.cos(t), r * np.sin(t), 0])

        mob = axes.plot_parametric_curve(
            polar, t_range=np.array([curve.get("t_min", 0), curve.get("t_max", 6.28), 0.01]))
    elif mode == "lorenz":
        xs, ys = lorenz_points()
        points = [axes.c2p(float(x), float(y)) for x, y in zip(xs, ys)]
        mob = VMobject()
        mob.set_points_as_corners(points)
    elif mode == "chords":
        n = int(curve.get("points", 200))
        k = int(curve.get("multiple", 3))
        r = float(curve.get("radius", 2.5))
        angs = 2 * np.pi * np.arange(n) / n
        pts = [axes.c2p(r * float(np.cos(a)), r * float(np.sin(a))) for a in angs]
        lines = []
        for i in range(n):
            line = Line(pts[i], pts[(i * k) % n])
            line.set_color(_gradient_color(i / max(1, n - 1)))
            line.set_stroke(width=2)
            lines.append(line)
        return VGroup(*lines), None
    elif mode == "dots":
        n = int(curve.get("n", 600))
        angle = float(np.deg2rad(curve.get("angle", 137.508)))
        spacing = float(curve.get("spacing", 0.12))
        dots = []
        for i in range(n):
            r = spacing * np.sqrt(i)
            a = i * angle
            dot = Dot(point=axes.c2p(r * float(np.cos(a)), r * float(np.sin(a))),
                      radius=0.04, color=_gradient_color(i / max(1, n - 1)))
            dots.append(dot)
        return VGroup(*dots), None
    else:
        raise ValueError(f"Unknown mode '{mode}'")
    # Colour along the drawing (butterfly: pink -> blue) or one colour
    # per wing (Lorenz): the segments are the visible drawing, the
    # original single path is what the dot follows.
    if curve.get("gradient"):
        c1, c2 = curve["gradient"][0], curve["gradient"][1]
        segs = _segments_from_mob(
            mob, lambda t, m, c1=c1, c2=c2: _lerp_hex(c1, c2, t), n_seg=600)
        return segs, mob
    if curve.get("wing_colors"):
        w1, w2 = curve["wing_colors"][0], curve["wing_colors"][1]
        segs = _segments_from_mob(
            mob, lambda t, m, w1=w1, w2=w2: w1 if m[0] < 0 else w2, n_seg=800)
        return segs, mob
    return mob, mob


class EquationCinema(MovingCameraScene):
    def construct(self):
        cfg = load_config()
        mode = cfg.get("mode", "y")
        camera_moves = bool(cfg.get("camera_moves", True))

        self.camera.background_color = "#050510"
        config.background_color = "#050510"
        if camera_moves:
            self.camera.frame.save_state()

        if mode == "showcase":
            all_mobs = self._showcase_sequence(cfg)
        elif mode == "morph-chords":
            all_mobs = self._morph_sequence(cfg)
        else:
            all_mobs = self._normal_sequence(cfg)

        # The finished picture holds, then one final pull-back.
        self.wait(1.5)
        if camera_moves:
            # Slow pull-back to the full wide view before the end.
            self.play(Restore(self.camera.frame), run_time=2.5)
        self.wait(1.2)
        self.play(FadeOut(VGroup(*all_mobs)), run_time=0.8)

    # ------------------------------------------------------------ normal
    def _normal_sequence(self, cfg):
        curves = curves_from_config(cfg)
        duration = float(cfg.get("duration", 8.0))
        per_curve = max(2.0, duration / len(curves))
        camera_moves = bool(cfg.get("camera_moves", True))
        camera_style = cfg.get("camera_style", "push-in") if camera_moves else "wide"
        text = cfg.get("text") or {}

        x_range, y_range = cfg["x_range"], cfg["y_range"]
        xl, yl = _axes_lengths(x_range, y_range)
        if camera_style == "zoom-out":
            # Start close (x0.62); each curve's draw pulls back a step,
            # so the finished picture is revealed gradually.
            self.camera.frame.scale(0.62)
            zoom_factor = (1 / 0.62) ** (1 / len(curves))

        plane = NumberPlane(
            x_range=[x_range[0], x_range[1], 1],
            y_range=[y_range[0], y_range[1], 1],
            x_length=xl, y_length=yl,
            background_line_style={"stroke_color": "#1e293b", "stroke_width": 1},
        )
        axes = Axes(
            x_range=[x_range[0], x_range[1], 1],
            y_range=[y_range[0], y_range[1], 1],
            x_length=xl, y_length=yl,
            axis_config={"color": "#64748b", "stroke_width": 2},
        )

        built = []
        for curve in curves:
            color = curve.get("color", "#22d3ee")
            mob, lap_path = _build_curve(axes, curve)
            if curve["mode"] in ("chords", "dots") or curve.get("gradient") or curve.get("wing_colors"):
                # Segments / chords / dots carry their own colours.
                glow = None
                if lap_path is not None:
                    lap_path.set_color(color).set_stroke(width=5)
            else:
                mob.set_color(color)
                mob.set_stroke(width=5)
                glow = mob.copy().set_color(color).set_stroke(width=16, opacity=0.18)
            built.append((mob, glow, color, lap_path))

        title = _title_mobject(cfg)
        title.set_color("#e2e8f0")
        first_color = built[0][2] if built else "#22d3ee"
        formula_line = _formula_mobject(cfg, first_color)

        fade_in = [FadeIn(plane), FadeIn(axes), Write(title)]
        if formula_line is not None:
            fade_in.append(FadeIn(formula_line))
        self.play(*fade_in, run_time=1.2)

        # Pin the title and the formula line to the visible frame, so
        # a zoom-out or a pan never clips them while the camera moves.
        # (Manim 0.19 has no fixed-in-frame mobjects for a 2D scene,
        # so the pin is an updater that tracks the camera frame.)
        def _pin_top(m):
            f = self.camera.frame
            m.set_y(f.get_center()[1] + f.height / 2 - 0.9 - m.height / 2)
            m.set_x(f.get_center()[0])

        def _pin_bottom(m):
            f = self.camera.frame
            m.set_y(f.get_center()[1] - f.height / 2 + 0.35 + m.height / 2)
            m.set_x(f.get_center()[0])

        title.add_updater(_pin_top)
        if formula_line is not None:
            formula_line.add_updater(_pin_bottom)

        all_mobs = [plane, axes, title]
        if formula_line is not None:
            all_mobs.append(formula_line)

        if cfg.get("simultaneous"):
            return self._simultaneous_draw(cfg, curves, built, all_mobs,
                                           per_curve, camera_style, zoom_factor
                                           if camera_style == "zoom-out" else None)

        first_curve = True
        for ci, (curve, (mob, glow, color, lap_path)) in enumerate(zip(curves, built)):
            mode = curve["mode"]
            # --- camera move for this curve's draw ---
            cam = self.camera.frame.animate
            if camera_style == "push-in":
                if first_curve:
                    cam = cam.scale(0.85)
                cam = cam.move_to(mob.get_center())
            elif camera_style == "zoom-out":
                cam = cam.scale(zoom_factor).move_to(mob.get_center())
            elif camera_style == "pan":
                # Smooth rewind to the start of the drawing, then pan
                # along it while it draws.
                if np.linalg.norm(
                        self.camera.frame.get_center() - _mob_start(mob)) > 0.5:
                    self.play(self.camera.frame.animate.move_to(_mob_start(mob)),
                              run_time=0.8)
                cam = cam.move_to(_mob_end(mob))
            # "wide": no camera animation at all.

            # --- draw this curve, once, the dot riding its tip ---
            dot = Dot(color="#ffffff", radius=0.09)
            dot.move_to(_mob_start(mob))
            # "wide" has no camera animation at all — never play an empty
            # .animate, it has nothing to do.
            cam_anim = None if camera_style == "wide" else cam
            # The dot rides the tip while the curve draws: Create and
            # MoveAlongPath run together, so the dot is the drawing.
            # No TracedPath trail: it only samples the dot once per
            # frame, so on curvy lines it joins those points with
            # straight chords and looks like a random wavy line.
            # No laps, no loops: the curve draws once and that is it.
            dot_anim = None
            if lap_path is not None:
                dot_anim = MoveAlongPath(dot, lap_path)
            if isinstance(mob, VGroup):
                # Chords, dots, or colour segments: appear piece by piece.
                if mode == "dots":
                    draw = LaggedStart(*[FadeIn(s) for s in mob],
                                      lag_ratio=0.01, run_time=per_curve)
                else:
                    draw = LaggedStart(*[Create(s) for s in mob],
                                      lag_ratio=0.02, run_time=per_curve)
                anims = [draw]
                if dot_anim is not None:
                    anims.append(dot_anim)
                if cam_anim is not None:
                    anims.append(cam_anim)
                self.play(*anims, run_time=per_curve)
            else:
                anims = [Create(glow), Create(mob)]
                if dot_anim is not None:
                    anims.append(dot_anim)
                if cam_anim is not None:
                    anims.append(cam_anim)
                self.play(*anims, run_time=per_curve)
            was_first = first_curve
            first_curve = False
            if glow is not None:
                all_mobs.append(glow)
            all_mobs += [mob, dot]

            # The title (and the formula line) leave once the picture
            # takes over — the pi reel's fade.
            if was_first and text.get("title_fades"):
                fades = [FadeOut(title)]
                if formula_line is not None:
                    fades.append(FadeOut(formula_line))
                self.play(*fades, run_time=0.6)

        return all_mobs

    # --------------------------------------- simultaneous (a race)
    def _simultaneous_draw(self, cfg, curves, built, all_mobs, per_curve,
                           camera_style, zoom_factor):
        """All curves draw at the same time, each with its own dot
        riding its tip — the growth race. Draw once, no laps."""
        mobs = [b[0] for b in built]
        glows = [b[1] for b in built]
        lap_paths = [b[3] for b in built]
        group = VGroup(*mobs)
        cam = self.camera.frame.animate
        if camera_style == "zoom-out" and zoom_factor is not None:
            cam = cam.scale(1 / 0.62).move_to(group.get_center())
        elif camera_style == "push-in":
            cam = cam.scale(0.85).move_to(group.get_center())
        else:
            cam = None
        duration = float(cfg.get("duration", 8.0))
        dots = []
        for mob in mobs:
            dot = Dot(color="#ffffff", radius=0.09)
            dot.move_to(_mob_start(mob))
            dots.append(dot)
        draw_anims = []
        for mob, glow, lap_path, dot in zip(mobs, glows, lap_paths, dots):
            if glow is not None:
                draw_anims.append(Create(glow))
            draw_anims.append(Create(mob))
            if lap_path is not None:
                draw_anims.append(MoveAlongPath(dot, lap_path))
        if cam is not None:
            self.play(*draw_anims, cam, run_time=duration)
        else:
            self.play(*draw_anims, run_time=duration)
        for mob, glow, dot in zip(mobs, glows, dots):
            if glow is not None:
                all_mobs.append(glow)
            all_mobs.append(mob)
            all_mobs.append(dot)
        return all_mobs

    # ------------------------------------------------------------ morph
    def _morph_sequence(self, cfg):
        """The full Power of 3 morph: dots on a number line, the line
        bends into a circle, the chords bloom into the cardioid."""
        n = int(cfg.get("points", 200))
        k = int(cfg.get("multiple", 3))
        r = float(cfg.get("radius", 2.5))
        text = cfg.get("text") or {}
        title = _title_mobject(cfg)
        title.set_color("#e2e8f0")
        caption = None
        if text.get("caption"):
            caption = Text(text["caption"], font_size=24, color="#22d3ee")
            caption.to_edge(DOWN, buff=0.35)

        line = Line([-6, 0, 0], [6, 0, 0], color="#64748b", stroke_width=2)
        tick_labels = VGroup()
        for i, num in [(0, "0"), (50, "50"), (100, "100"), (150, "150"), (n - 1, str(n))]:
            x = -6 + 12 * i / max(1, n - 1)
            tick_labels.add(Text(num, font_size=20, color="#94a3b8").move_to([x, -0.45, 0]))
        line_dots = VGroup(*[
            Dot(point=[-6 + 12 * i / max(1, n - 1), 0, 0], radius=0.03, color="#22d3ee")
            for i in range(n)])
        intro = [FadeIn(line), FadeIn(tick_labels), FadeIn(line_dots), FadeIn(title)]
        if caption is not None:
            intro.append(FadeIn(caption))
        self.play(*intro, run_time=1.0)

        # The line bends into a circle.
        angs = 2 * np.pi * np.arange(n) / n
        target_dots = VGroup(*[
            Dot(point=[r * float(np.cos(a)), r * float(np.sin(a)), 0],
                radius=0.03, color="#22d3ee")
            for a in angs])
        circle = Circle(radius=r, color="#e2e8f0", stroke_width=2, stroke_opacity=0.5)
        self.play(Transform(line_dots, target_dots), Create(circle),
                  FadeOut(line), FadeOut(tick_labels), run_time=3.0)

        # The chords bloom.
        chords = _circle_chords(n, k, r)
        self.play(LaggedStart(*[Create(c) for c in chords],
                              lag_ratio=0.02, run_time=6.0))

        all_mobs = [title, circle, line_dots, chords]
        if caption is not None:
            all_mobs.append(caption)
        return all_mobs

    # --------------------------------------------------------- showcase
    def _showcase_sequence(self, cfg):
        """Five equations, one after another, hard cuts, 3 s each, on
        a faint polar grid — the fast roses-showcase format."""
        items = cfg.get("items", [])
        x_range, y_range = cfg["x_range"], cfg["y_range"]
        xl, yl = _axes_lengths(x_range, y_range)
        # Hidden axes: only used to map data coords to the screen.
        axes = Axes(
            x_range=[x_range[0], x_range[1], 1],
            y_range=[y_range[0], y_range[1], 1],
            x_length=xl, y_length=yl,
            axis_config={"color": "#64748b", "stroke_width": 2},
        )
        # Faint polar grid: concentric circles + spokes.
        unit = xl / (x_range[1] - x_range[0])
        grid = VGroup()
        for rad in (1, 2, 3):
            grid.add(Circle(radius=rad * unit, color="#1e293b", stroke_width=1))
        for j in range(12):
            a = 2 * np.pi * j / 12
            grid.add(Line([0, 0, 0],
                          [3 * unit * float(np.cos(a)), 3 * unit * float(np.sin(a)), 0],
                          color="#1e293b", stroke_width=1))
        self.play(FadeIn(grid), run_time=0.8)

        for item in items:
            color = item.get("color", "#22d3ee")
            mob, _ = _build_curve(axes, item)
            mob.set_color(color)
            mob.set_stroke(width=5)
            glow = mob.copy().set_color(color).set_stroke(width=16, opacity=0.18)
            if USE_TEX:
                try:
                    eq = MathTex(item["latex"]).scale(0.7).to_edge(UP, buff=0.9)
                except Exception:
                    eq = Text(item["label"], font_size=30).to_edge(UP, buff=0.9)
            else:
                eq = Text(item["label"], font_size=30).to_edge(UP, buff=0.9)
            eq.set_color(color)
            self.play(FadeIn(eq), Create(glow), Create(mob), run_time=3.0)
            self.wait(0.7)
            self.play(FadeOut(eq), FadeOut(glow), FadeOut(mob), run_time=0.3)
        return [grid]

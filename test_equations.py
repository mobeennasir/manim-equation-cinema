"""Quick checks that do NOT need Manim — run before your first render:
    python test_equations.py
"""
from audio import AUDIO, audio_for
from equations import PRESETS, config_from_preset, validate_config


def main():
    CAMERA_STYLES = {"push-in", "zoom-out", "pan", "wide"}
    for name in sorted(PRESETS):
        p = PRESETS[name]
        # Every preset defines its story, camera and on-screen text in this file.
        assert p.get("story"), f"{name}: missing 'story'"
        assert p.get("camera_style") in CAMERA_STYLES, f"{name}: bad camera_style"
        assert p.get("camera_note"), f"{name}: missing 'camera_note'"
        assert isinstance(p.get("text"), dict), f"{name}: missing 'text' dict"
        cfg = config_from_preset(name)
        assert cfg.get("story") and cfg.get("camera_style") and isinstance(cfg.get("text"), dict), \
            f"{name}: story/camera/text did not travel into the config"
        if p["mode"] == "showcase":
            assert len(cfg["items"]) >= 2, f"{name}: showcase needs 2+ items"
            for item in cfg["items"]:
                assert item.get("label") and item.get("latex"), f"{name}: showcase item needs label + latex"
        if p["mode"] == "morph-chords":
            assert cfg["points"] >= 50 and cfg["multiple"] >= 2, f"{name}: bad morph params"
        info = validate_config(cfg)
        stars = "★" * cfg.get("viral", 3) + "☆" * (5 - cfg.get("viral", 3))
        a = audio_for(cfg)
        print(f"OK  {name:16s} {len(cfg['curves'])} curve(s)  {info['finite_points']} points  "
              f"viral {stars}  camera {cfg['camera_style']:9s}  audio: {a['song']} ({a['language']})")
    cfg = {"mode": "y", "expr": "sin(x)^2 + cos(x)", "x_min": -6.28, "x_max": 6.28}
    print("OK  custom y=sin(x)^2+cos(x):", validate_config(cfg)["finite_points"], "points")
    assert set(AUDIO) >= {"butterfly", "lorenz", "rose", "heart", "calm"}, "audio keys missing"
    print(f"\nAll {len(PRESETS)} presets + custom equation pass. "
          f"Audio suggestions: {len(AUDIO)} keys. Manim itself is NOT tested here.")


if __name__ == "__main__":
    main()

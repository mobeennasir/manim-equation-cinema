"""
audio.py — viral audio suggestions for each video.

IMPORTANT, read this before you post:
- The Manim .mp4 is SILENT. Manim does not add music.
- This file tells you WHICH song to add in Instagram / CapCut / VN
  when you post the video, and WHERE in the song to start.
- Timestamps are APPROXIMATE (different uploads / versions shift by a
  few seconds). Always check the hook in the Instagram music picker
  before you post — start the clip at the chorus / drop, not at 0:00.
- Use the song through Instagram's own music sticker / audio library
  when you post, so the audio is licensed for the platform. Do not
  burn a downloaded song into the mp4 and re-upload it elsewhere.

Each entry: song, artist, language, start/end in seconds for a ~15s
reel clip, the moment to hit, and why it fits this curve.
"""

# start/end are seconds into the song. "moment" is what happens there.
AUDIO = {
    "butterfly": {
        "song": "Cornfield Chase", "artist": "Hans Zimmer (Interstellar)",
        "language": "English / instrumental", "start": 42, "end": 57,
        "moment": "0:42 — the piano build lifts into the main theme",
        "why": "Epic and emotional, builds exactly as the butterfly finishes drawing. The reel that inspired this project used this kind of cinematic build.",
        "tip": "Start the video 1 second before the music lifts, so the wings finish as the theme peaks.",
    },
    "lorenz": {
        "song": "Space Song", "artist": "Beach House",
        "language": "English", "start": 0, "end": 15,
        "moment": "0:00 — dreamy opening, 'it was late at night'",
        "why": "Dreamy and floating, perfect for chaos that never repeats. Very popular on aesthetic / space reels.",
        "tip": "Loop the opening — it is calm enough that the chaos on screen does the work.",
    },
    "rose": {
        "song": "Pasoori", "artist": "Ali Sethi & Shae Gill (Coke Studio Pakistan)",
        "language": "Punjabi / Urdu — Pakistani", "start": 48, "end": 63,
        "moment": "0:48 — chorus, 'Pasoori nu...'",
        "why": "The biggest Pakistani viral song of recent years. A flower blooming on the chorus is made for it.",
        "tip": "Time the last petal to land exactly on the first chorus beat.",
    },
    "heart": {
        "song": "Saiyaara", "artist": "Faheem Abdullah (Saiyaara, 2025)",
        "language": "Hindi — Indian", "start": 55, "end": 70,
        "moment": "0:55 — chorus, 'Saiyaara, tu to badla nahi hai...'",
        "why": "The most viral romantic song of 2025. A maths heart + this chorus is a classic save-and-share combo.",
        "tip": "Alternative, softer: 'Tum Hi Ho' (Arijit Singh), start ~0:40, the chorus.",
    },
    "spirograph": {
        "song": "Kesariya", "artist": "Arijit Singh (Brahmastra)",
        "language": "Hindi — Indian", "start": 32, "end": 47,
        "moment": "0:32 — 'Kesariya tera ishq hai piya...'",
        "why": "Warm, colourful and hugely used on aesthetic reels. Matches a colourful Spirograph perfectly.",
        "tip": "Use the flute-led part — it feels playful, like the toy.",
    },
    "lissajous": {
        "song": "Chaleya", "artist": "Arijit Singh (Jawan)",
        "language": "Hindi — Indian", "start": 45, "end": 60,
        "moment": "0:45 — chorus groove kicks in",
        "why": "Groovy and rhythmic — the Lissajous pattern moves like a beat. Good for a looped reel.",
        "tip": "Cut the video to the beat: one loop of the pattern per bar.",
    },
    "spiral": {
        "song": "Kun Faya Kun", "artist": "A. R. Rahman (Rockstar)",
        "language": "Hindi / Urdu — Indian", "start": 62, "end": 77,
        "moment": "1:02 — the qawwali build, 'Kun faya kun...'",
        "why": "Spiritual and endless, like a spiral that never ends. The golden spiral + this song is a 'nature follows maths' post.",
        "tip": "Let the spiral keep growing through the whole 15 seconds — do not cut early.",
    },
    "waves": {
        "song": "Until I Found You", "artist": "Stephen Sanchez",
        "language": "English", "start": 20, "end": 35,
        "moment": "0:20 — 'Georgia, wrap me up in all your...'",
        "why": "Soft, romantic, and one of the most used reel songs ever. Waves + this song = calm, shareable.",
        "tip": "For the 3-wave version, start each new coloured wave as the vocal line changes.",
    },
    "fourier": {
        "song": "Experience", "artist": "Ludovico Einaudi",
        "language": "Instrumental / piano", "start": 70, "end": 85,
        "moment": "1:10 — the piano theme returns, louder",
        "why": "Each new wave is a new layer of the music. The build matches the square wave forming, step by step.",
        "tip": "Add one coloured wave per piano phrase — the viewer hears the maths building.",
    },
    "calm": {
        "song": "Apocalypse", "artist": "Cigarettes After Sex",
        "language": "English", "start": 0, "end": 15,
        "moment": "0:00 — slow, dreamy opening",
        "why": "Slow and dreamy, the default sound of aesthetic maths reels. Never fights the visuals.",
        "tip": "If you want Pakistani instead: 'Afreen Afreen' (Rahat Fateh Ali Khan), start ~0:50, the chorus.",
    },
}

# Fallback for a custom equation with no preset audio.
DEFAULT_AUDIO_KEY = "calm"


def audio_for(cfg):
    """Return the audio suggestion dict for a config (preset key or vibe)."""
    key = cfg.get("audio") or cfg.get("preset") or DEFAULT_AUDIO_KEY
    # cfg["audio"] already stores the audio key (e.g. "butterfly", "rose").
    if key in AUDIO:
        return dict(AUDIO[key], key=key)
    return dict(AUDIO[DEFAULT_AUDIO_KEY], key=DEFAULT_AUDIO_KEY)


def fmt_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def audio_line(cfg):
    """One-line summary, e.g. for the command line after a render."""
    a = audio_for(cfg)
    return (f"🎵 Audio: {a['song']} — {a['artist']} ({a['language']}) | "
            f"use {fmt_time(a['start'])}–{fmt_time(a['end'])} approx. — {a['moment']}")

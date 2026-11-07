"""Make title / middle / end cards for the portrait demo video (1080x1920)."""
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BG = (5, 5, 16)
CYAN = (34, 211, 238)
ROSE = (251, 113, 133)
GOLD = (245, 158, 11)
WHITE = (226, 232, 240)
GREY = (148, 163, 184)


def font(size, bold=True):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else \
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size)


def card(path, lines):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # three coloured dots, like the three roses
    for i, c in enumerate((CYAN, ROSE, GOLD)):
        d.ellipse([440 + i * 100, 560, 500 + i * 100, 620], fill=c)
    y = 700
    for text, f, color in lines:
        w = d.textlength(text, font=f)
        d.text(((W - w) / 2, y), text, font=f, fill=color)
        y += f.size + 36
    img.save(path)
    print("saved", path)


card("/tmp/demo-recording/card-title.png", [
    ("Manim", font(150), CYAN),
    ("Equation Cinema", font(84), WHITE),
    ("Type any equation.", font(56), GREY),
    ("Get a cinematic video.", font(56), GREY),
])
card("/tmp/demo-recording/card-render.png", [
    ("Rendering in Manim...", font(72), GOLD),
    ("(sped up — real render", font(48), GREY),
    ("takes about 20 seconds)", font(48), GREY),
])
card("/tmp/demo-recording/card-end.png", [
    ("Your video is ready.", font(72), CYAN),
    ("Preview it. Download it.", font(52), WHITE),
    ("Add Pasoori 0:48-1:03", font(52), ROSE),
    ("when you post it.", font(52), WHITE),
    ("", font(52), WHITE),
    ("Built with Manim", font(44), GREY),
    ("(3Blue1Brown's engine)", font(44), GREY),
])

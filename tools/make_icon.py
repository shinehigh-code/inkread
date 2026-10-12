"""生成应用图标 assets/icon.ico（黛青底 + 墨字方印）。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon.ico"
SIZE = 256
ACCENT = (61, 90, 128, 255)
PAPER = (244, 241, 232, 255)
FRAME = (237, 233, 223, 235)


def main():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 6, SIZE - 6, SIZE - 6], radius=54, fill=ACCENT)
    d.rounded_rectangle([26, 26, SIZE - 26, SIZE - 26], radius=38, outline=FRAME, width=6)

    font = None
    for path in (r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc"):
        try:
            font = ImageFont.truetype(path, 152)
            break
        except OSError:
            continue
    if font is None:  # 兜底
        font = ImageFont.load_default()

    text = "墨"
    box = d.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((SIZE - w) / 2 - box[0], (SIZE - h) / 2 - box[1] - 6), text, font=font, fill=PAPER)

    OUT.parent.mkdir(exist_ok=True)
    img.save(OUT, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    img.resize((128, 128)).save(ROOT / "web" / "assets" / "logo.png")
    print("图标已生成：", OUT)


if __name__ == "__main__":
    main()

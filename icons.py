import os
from typing import Optional

from PIL import Image, ImageDraw


def load_icon_from_file(path: str, size: int = 64) -> Optional[Image.Image]:
    if not os.path.isfile(path):
        return None
    try:
        with Image.open(path) as src:
            return src.convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        return None


def create_fallback_icon(state: str, size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if state == "on":
        bg = (0, 180, 0, 255)
        mark = "check"
    elif state == "off":
        bg = (200, 0, 0, 255)
        mark = "cross"
    else:
        bg = (120, 120, 120, 255)
        mark = "q"

    margin = 8
    draw.ellipse((margin, margin, size - margin, size - margin), fill=bg)

    if mark == "check":
        draw.line((20, 34, 29, 44), fill=(255, 255, 255, 255), width=6)
        draw.line((29, 44, 46, 22), fill=(255, 255, 255, 255), width=6)
    elif mark == "cross":
        draw.line((22, 22, 44, 44), fill=(255, 255, 255, 255), width=6)
        draw.line((44, 22, 22, 44), fill=(255, 255, 255, 255), width=6)
    else:
        draw.arc((20, 16, 44, 40), start=0, end=180, fill=(255, 255, 255, 255), width=6)
        draw.line((32, 32, 32, 40), fill=(255, 255, 255, 255), width=6)
        draw.ellipse((29, 46, 35, 52), fill=(255, 255, 255, 255))

    return img

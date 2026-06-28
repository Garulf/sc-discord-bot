"""Render the inventory status ASCII table as a PNG image."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONT_PATH = Path(__file__).parent / "fonts" / "LiberationMono-Regular.ttf"
_FONT_SIZE = 14
_PADDING = 16
_BG_COLOR = (43, 45, 49, 255)  # #2b2d31 — Discord dark theme
_TEXT_COLOR = (220, 221, 222)  # #dcddde — Discord primary text

_font = ImageFont.truetype(str(_FONT_PATH), _FONT_SIZE)


def build_status_image(table: str) -> BytesIO:
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), table, font=_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    img = Image.new("RGBA", (text_w + _PADDING * 2, text_h + _PADDING * 2), _BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw.text((_PADDING, _PADDING), table, font=_font, fill=_TEXT_COLOR)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

INPUT_PATH = Path("input/image-1.png")
OUTPUT_PATH = Path("output/image-1.json")
BOXES_PATH = Path("output/image-1-boxes.png")
MASKED_PATH = Path("output/image-1-masked.png")

PROMPT = """
Find all Russian text on this engineering drawing.

Return JSON only: a list of objects with:
- text_ru: original Russian text
- text_en: English translation (abbreviations -> translit, e.g. alike ГОСТ->GOST, СБ->SB)
- box: [ymin, xmin, ymax, xmax] normalized 0-1000
- orientation: "horizontal" | "vertical" | "upside_down"

Skip numbers with no text (45, 130, Ø20, etc).
Keep translations short so they fit in table cells.
"""


def call_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY missing in .env")

    image_bytes = INPUT_PATH.read_bytes()

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(response.text, encoding="utf-8")
    print(response.text)
    print(f"\nsaved to {OUTPUT_PATH}")


def draw_debug_boxes():
    items = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    img = Image.open(INPUT_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    font = ImageFont.load_default()

    for item in items:
        if "box" not in item:
            continue
        ymin, xmin, ymax, xmax = item["box"]
        x0 = xmin / 1000 * w
        y0 = ymin / 1000 * h
        x1 = xmax / 1000 * w
        y1 = ymax / 1000 * h
        draw.rectangle([x0, y0, x1, y1], outline="red", width=2)
        label = item.get("text_ru", "")
        if label:
            draw.text((x0, max(0, y0 - 10)), label, fill="red", font=font)

    BOXES_PATH.parent.mkdir(exist_ok=True)
    img.save(BOXES_PATH)
    print(f"saved debug boxes to {BOXES_PATH}")


def box_to_pixels(box, w, h, inset=2):
    ymin, xmin, ymax, xmax = box
    x0 = xmin / 1000 * w + inset
    y0 = ymin / 1000 * h + inset
    x1 = xmax / 1000 * w - inset
    y1 = ymax / 1000 * h - inset
    return [x0, y0, x1, y1]


def mask_russian():
    items = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    img = Image.open(INPUT_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    for item in items:
        if "box" not in item:
            continue
        draw.rectangle(box_to_pixels(item["box"], w, h), fill="white")

    MASKED_PATH.parent.mkdir(exist_ok=True)
    img.save(MASKED_PATH)
    print(f"saved masked image to {MASKED_PATH}")


if __name__ == "__main__":
    # call_gemini()
    # draw_debug_boxes()
    mask_russian()

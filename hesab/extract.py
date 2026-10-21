"""PDF pages -> structured rows via Gemini vision."""

import os
import time
from collections.abc import Callable

import numpy as np
import pymupdf
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

DEFAULT_MODEL = "gemini-2.5-flash"


class Row(BaseModel):
    date: str = Field(description="Date cell as MM/DD with Latin digits, e.g. '07/05'")
    weekday: str | None = Field(None, description="Weekday cell exactly as printed, in Persian")
    in1: str | None = Field(None, description="ورود۱ as written")
    out1: str | None = Field(None, description="خروج۱ as written")
    in2: str | None = Field(None, description="ورود۲ as written")
    out2: str | None = Field(None, description="خروج۲ as written")
    mission_from: str | None = Field(None, description="ساعت ماموریت 'از' value")
    mission_to: str | None = Field(None, description="ساعت ماموریت 'تا' value")
    remote: str | None = Field(None, description="ساعت دورکاری cell as written (number or text)")
    written_total: str | None = Field(
        None, description="جمع کارکرد روزانه exactly as handwritten (used only to cross-check, not trusted)"
    )
    note: str | None = Field(None, description="Anything unusual about this row, in Persian or English")
    uncertain_fields: list[str] = Field(
        default_factory=list,
        description="Names of fields in this row whose reading is uncertain",
    )


class PageData(BaseModel):
    name: str = Field(description="Person name after 'نام و نام خانوادگی:' in Persian")
    year: str | None = Field(None, description="Year in the header, Latin digits, e.g. '1405'")
    rows: list[Row]


PROMPT = """\
This is a scanned Persian employee attendance form (فرم حضور و غیاب کارکنان).
Transcribe it into the JSON schema. Rules:

- The table is right-to-left. Columns from right to left:
  تاریخ | روز | ورود۱ | خروج۱ | ورود۲ | خروج۲ | ساعت ماموریت (از ... تا ...) | ساعت دورکاری | جمع کارکرد روزانه
- Output one row for EVERY printed date row, including empty and shaded (Friday) rows.
- Convert all Persian/Arabic digits to Latin digits. Write times as H:MM (e.g. '9,30' -> '9:30',
  '14,-' -> '14:00', '17' -> '17:00', '8.30' -> '8:30'). Values like '24:30' are valid (after midnight).
- A dash, line or empty cell means null. Ignore the printed placeholder 'از...... تا......' when nothing
  handwritten is filled in.
- In the ماموریت column, put the handwritten 'از' time in mission_from and the 'تا' time in mission_to.
- In ساعت دورکاری put hours as written (e.g. '2', '1:30'). If it contains a word (e.g. 'ماموریت')
  or ditto marks (//) instead of a number, put that text in remote as-is.
- Copy the جمع کارکرد روزانه column into written_total exactly as written (e.g. '9:30', '8'). Do not
  compute anything yourself. Ignore monthly totals written outside the table.
- If a value is crossed out and a correction is written nearby (also below the table), use the correction
  for that row and mention it in note.
- Some people write Persian digits, others Latin digits. Look closely at each digit: Persian ۸ is an
  inverted V and ۶ has a tail; in Latin handwriting 8 has two loops and 6 one loop. Typical exit times
  are in the afternoon/evening, but read what is written, do not guess.
- Read each row strictly along its own horizontal line; never copy a value from the row above or below.
- List any field you are not sure about in uncertain_fields (use the schema field names).
"""

MULTI_PAGE = """
There are {n} page images below, each preceded by its label 'Page N'. Return exactly {n} entries in
`pages`, in the same order, one per image, even if a page looks like a duplicate or is mostly empty.
"""


MAX_REQUEST_BYTES = 18 * 1024 * 1024  # Gemini inline request limit is 20 MB


class Document(BaseModel):
    pages: list[PageData] = Field(description="One entry per input page, in the same order")


def table_rect(page: pymupdf.Page) -> pymupdf.Rect:
    """Bounding box of the ruled table (found from its long border lines), padded so the year
    printed above it and notes written next to or below it stay in view. Falls back to the whole page."""
    pix = page.get_pixmap(dpi=50, colorspace=pymupdf.csGRAY)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.stride)[:, : pix.w]
    dark = img < 110
    rows = np.flatnonzero(dark.mean(axis=1) > 0.4)
    if len(rows) < 2:
        return page.rect
    cols = np.flatnonzero(dark[rows[0] : rows[-1] + 1].mean(axis=0) > 0.4)
    if len(cols) < 2:
        return page.rect
    sx, sy = page.rect.width / pix.w, page.rect.height / pix.h
    w, h = page.rect.width, page.rect.height
    rect = pymupdf.Rect(cols[0] * sx - 0.06 * w, rows[0] * sy - 0.10 * h,
                        cols[-1] * sx + 0.06 * w, rows[-1] * sy + 0.10 * h)
    return rect & page.rect


def render_pages(pdf_path: str, dpi: int = 300) -> list[bytes]:
    """Render each page's table as JPEG, lowering resolution until all fit in one request."""
    doc = pymupdf.open(pdf_path)
    try:
        clips = [table_rect(page) for page in doc]
        for d, quality in ((dpi, 85), (220, 80), (150, 75)):
            images = [page.get_pixmap(dpi=d, clip=clip).tobytes("jpeg", jpg_quality=quality)
                      for page, clip in zip(doc, clips)]
            if sum(len(i) for i in images) <= MAX_REQUEST_BYTES:
                break
        return images
    finally:
        doc.close()


def make_client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set (get a free key at https://aistudio.google.com/apikey)")
    return genai.Client(api_key=key)


def extract_images(client: genai.Client, images: list[bytes], model: str, retries: int = 4) -> list[PageData]:
    """All pages in a single request."""
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=Document,
        temperature=0,
        max_output_tokens=65536,
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
    )
    contents: list = [PROMPT + MULTI_PAGE.format(n=len(images))]
    for i, image in enumerate(images, start=1):
        contents += [f"Page {i}:", types.Part.from_bytes(data=image, mime_type="image/jpeg")]
    delay = 15.0
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=config)
            doc = resp.parsed if resp.parsed is not None else Document.model_validate_json(resp.text)
            return doc.pages
        except Exception as e:  # rate limits / transient server errors
            msg = str(e)
            if attempt == retries - 1 or not any(
                code in msg for code in ("429", "500", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")
            ):
                raise
            time.sleep(delay)
            delay *= 2
    raise AssertionError("unreachable")


def extract_pdf(
    pdf_path: str,
    model: str | None = None,
    status: Callable[[str], None] | None = None,
) -> list[PageData]:
    model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
    client = make_client()
    images = render_pages(pdf_path)
    if status:
        status(f"sending {len(images)} pages to {model} in one request")
    pages = extract_images(client, images, model)
    if len(pages) != len(images):
        raise RuntimeError(f"model returned {len(pages)} pages for {len(images)} input pages")
    return pages

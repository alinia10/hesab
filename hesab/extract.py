"""PDF pages -> structured rows via Gemini vision."""

import os
import time
from collections.abc import Callable

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
- IGNORE the جمع کارکرد روزانه column and any monthly total written outside the table; do not compute anything.
- If a value is crossed out and a correction is written nearby (also below the table), use the correction
  for that row and mention it in note.
- List any field you are not sure about in uncertain_fields (use the schema field names).
"""


def render_pages(pdf_path: str, dpi: int = 200) -> list[bytes]:
    doc = pymupdf.open(pdf_path)
    try:
        return [page.get_pixmap(dpi=dpi).tobytes("jpeg", jpg_quality=85) for page in doc]
    finally:
        doc.close()


def make_client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set (get a free key at https://aistudio.google.com/apikey)")
    return genai.Client(api_key=key)


def extract_page(client: genai.Client, image: bytes, model: str, retries: int = 5) -> PageData:
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=PageData,
        temperature=0,
    )
    contents = [types.Part.from_bytes(data=image, mime_type="image/jpeg"), PROMPT]
    delay = 10.0
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=config)
            if resp.parsed is not None:
                return resp.parsed
            return PageData.model_validate_json(resp.text)
        except Exception as e:  # rate limits / transient server errors
            if attempt == retries - 1:
                raise
            msg = str(e)
            if not any(code in msg for code in ("429", "500", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")):
                raise
            time.sleep(delay)
            delay *= 2
    raise AssertionError("unreachable")


def extract_pdf(
    pdf_path: str,
    model: str | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[PageData]:
    model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
    client = make_client()
    images = render_pages(pdf_path)
    pages = []
    for i, image in enumerate(images):
        if progress:
            progress(i, len(images))
        pages.append(extract_page(client, image, model))
    if progress:
        progress(len(images), len(images))
    return pages

"""One-shot PDF -> xlsx pipeline shared by the CLI and the web UI."""

import json
from collections.abc import Callable

from dotenv import load_dotenv

from .build import Month, build_month
from .excel import write_workbook
from .extract import PageData, extract_pdf

load_dotenv()


def convert(
    pdf_path: str,
    model: str | None = None,
    status: Callable[[str], None] | None = None,
) -> tuple[bytes, Month, list[PageData]]:
    pages = extract_pdf(pdf_path, model=model, status=status)
    month = build_month(pages)
    return write_workbook(month), month, pages


def convert_json(json_path: str) -> tuple[bytes, Month, list[PageData]]:
    """Rebuild the workbook from a saved extraction (no API calls)."""
    with open(json_path, encoding="utf-8") as f:
        pages = [PageData.model_validate(p) for p in json.load(f)]
    month = build_month(pages)
    return write_workbook(month), month, pages


def dump_pages(pages: list[PageData], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump([p.model_dump() for p in pages], f, ensure_ascii=False, indent=1)

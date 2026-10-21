import argparse
import sys
from pathlib import Path

from .pipeline import convert, convert_json, dump_pages


def fmt(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"


def main() -> None:
    ap = argparse.ArgumentParser(prog="hesab", description="Attendance PDF -> Excel")
    ap.add_argument("input", help="scanned PDF (or a .json saved with --save-json)")
    ap.add_argument("-o", "--output", help="output .xlsx (default: next to the input)")
    ap.add_argument("--model", help="Gemini model (default: $GEMINI_MODEL or gemini-2.5-flash)")
    ap.add_argument("--save-json", action="store_true", help="also save the raw extraction as .json")
    args = ap.parse_args()

    src = Path(args.input)
    out = Path(args.output) if args.output else src.with_suffix(".xlsx")

    if src.suffix.lower() == ".json":
        data, month, pages = convert_json(str(src))
    else:
        try:
            data, month, pages = convert(
                str(src), model=args.model, status=lambda m: print(m, "...", file=sys.stderr, flush=True)
            )
        except Exception as e:
            sys.exit(f"error: {e}")
        if args.save_json:
            dump_pages(pages, str(src.with_suffix(".json")))

    out.write_bytes(data)
    print(f"{len(pages)} pages, month {month.month:02d}/{month.year or '?'} -> {out}")
    for p in month.people:
        worked = [d for d in p.days if d.total > 0]
        flagged = sum(1 for d in p.days if d.flags)
        print(f"  {p.name}: {len(worked)} days, {fmt(sum(d.total for d in p.days))} h"
              + (f", {flagged} rows to check" if flagged else ""))


if __name__ == "__main__":
    main()

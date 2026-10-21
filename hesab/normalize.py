"""Text normalization: digits, times, names, weekdays."""

import re

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]


def to_latin(s: str) -> str:
    return s.translate(_DIGITS)


def parse_time(s: str | None) -> int | None:
    """'9:30', '9,30', '14,-', '17', '1610', '24:30' -> minutes since midnight. None if unparseable."""
    if s is None:
        return None
    s = to_latin(s).strip().strip("'\"’`~-—_ ").replace("٫", ":").replace("،", ":")
    if not s:
        return None
    s = re.sub(r"[,./;\s]+", ":", s)
    m = re.fullmatch(r"(\d{1,2})(?::(\d{0,2}))?[:\-~]*", s)
    if m:
        h, mm = int(m.group(1)), int(m.group(2) or 0)
    elif re.fullmatch(r"\d{3,4}", s):  # '1610' -> 16:10, '930' -> 9:30
        h, mm = int(s[:-2]), int(s[-2:])
    else:
        return None
    if h > 30 or mm >= 60:
        return None
    return h * 60 + mm


def parse_hours(s: str | None) -> int | None:
    """Duration in hours ('2', '1:30', '1.5') -> minutes. None if not numeric."""
    if s is None:
        return None
    t = to_latin(s).strip()
    if re.fullmatch(r"\d+(\.\d+)?", t) and "." in t:
        return round(float(t) * 60)
    return parse_time(t)


def name_key(name: str) -> str:
    n = name.replace("ي", "ی").replace("ك", "ک").replace("‌", "")
    return re.sub(r"\s+", "", n)


def norm_weekday(s: str | None) -> str | None:
    if not s:
        return None
    k = name_key(s)
    for w in WEEKDAYS:
        if name_key(w) == k:
            return w
    return None


def norm_date(s: str) -> tuple[int, int] | None:
    nums = re.findall(r"\d+", to_latin(s))
    if len(nums) < 2:
        return None
    month, day = int(nums[-2]), int(nums[-1])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return month, day

"""Group extracted pages by person, fill the month calendar, validate."""

from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .extract import PageData
from .normalize import WEEKDAYS, name_key, norm_date, norm_weekday, parse_hours, parse_time, to_latin

TIME_FIELDS = ["in1", "out1", "in2", "out2", "mission_from", "mission_to"]
PAIRS = [("in1", "out1"), ("in2", "out2"), ("mission_from", "mission_to")]


@dataclass
class Day:
    day: int
    weekday: str | None = None
    times: dict[str, int | None] = field(default_factory=lambda: dict.fromkeys(TIME_FIELDS))
    remote: int | None = None  # minutes
    notes: list[str] = field(default_factory=list)
    flags: set[str] = field(default_factory=set)  # fields to highlight
    on_page: bool = False  # row was present in the scan

    @property
    def total(self) -> int:
        t = 0
        for a, b in PAIRS:
            x, y = self.times[a], self.times[b]
            if x is not None and y is not None:
                t += (y - x) % (24 * 60)
        return t + (self.remote or 0)


@dataclass
class Person:
    name: str
    days: list[Day]


@dataclass
class Month:
    year: str | None
    month: int
    people: list[Person]


def month_length(month: int, max_seen: int) -> int:
    base = 31 if month <= 6 else 30 if month <= 11 else 29
    return max(base, max_seen)


def _group_names(pages: list[PageData]) -> list[list[PageData]]:
    groups: list[tuple[str, list[PageData]]] = []
    for p in pages:
        key = name_key(p.name)
        for gkey, members in groups:
            if gkey == key or SequenceMatcher(None, gkey, key).ratio() >= 0.85:
                members.append(p)
                break
        else:
            groups.append((key, [p]))
    return [members for _, members in groups]


def _fill_row(d: Day, row) -> None:
    d.on_page = True
    d.weekday = d.weekday or norm_weekday(row.weekday)
    for f in TIME_FIELDS:
        raw = getattr(row, f)
        if raw is None or not str(raw).strip():
            continue
        v = parse_time(raw)
        if v is None:
            d.flags.add(f)
            d.notes.append(f"{f}: '{raw}' خوانا نیست")
        elif d.times[f] is None:
            d.times[f] = v
    if row.remote and row.remote.strip():
        v = parse_hours(row.remote)
        if v is None:
            d.notes.append(f"دورکاری: {row.remote.strip()}")
            d.flags.add("remote")
        else:
            d.remote = v
    if row.note:
        d.notes.append(row.note.strip())
    d.flags.update(f for f in row.uncertain_fields if f in TIME_FIELDS or f == "remote")


def _validate(d: Day) -> None:
    for a, b in PAIRS:
        x, y = d.times[a], d.times[b]
        if (x is None) != (y is None):
            d.flags.update({a, b})
            d.notes.append(f"{a}/{b}: فقط یکی ثبت شده")
        elif x is not None and y is not None and y <= x:
            d.flags.update({a, b})
            d.notes.append(f"{a}/{b}: خروج قبل از ورود (بعد از نیمه‌شب فرض شد)")
    if d.total > 16 * 60:
        d.flags.add("total")
        d.notes.append("کارکرد بیش از ۱۶ ساعت")


def build_month(pages: list[PageData]) -> Month:
    months = Counter()
    years = Counter()
    for p in pages:
        if p.year:
            years[to_latin(p.year).strip()] += 1
        for r in p.rows:
            md = norm_date(r.date)
            if md:
                months[md[0]] += 1
    if not months:
        raise ValueError("no dated rows found in the PDF")
    month = months.most_common(1)[0][0]
    year = years.most_common(1)[0][0] if years else None

    # weekday anchor shared by everyone: (day, weekday index)
    anchors = Counter()
    people = []
    max_seen = 0
    for group in _group_names(pages):
        display = Counter(p.name.strip() for p in group).most_common(1)[0][0]
        days: dict[int, Day] = {}
        for p in group:
            for r in p.rows:
                md = norm_date(r.date)
                if not md or md[0] != month:
                    continue
                d = days.setdefault(md[1], Day(md[1]))
                _fill_row(d, r)
                if d.weekday:
                    anchors[(md[1] - WEEKDAYS.index(d.weekday)) % 7] += 1
                max_seen = max(max_seen, md[1])
        people.append((display, days))

    n = month_length(month, max_seen)
    offset = anchors.most_common(1)[0][0] if anchors else None
    result = []
    for display, days in people:
        full = []
        for i in range(1, n + 1):
            d = days.get(i) or Day(i)
            if offset is not None:
                d.weekday = WEEKDAYS[(i - offset) % 7]
            if d.on_page:
                _validate(d)
            else:
                d.notes.append("صفحه این روز در فایل نیست")
            full.append(d)
        result.append(Person(display, full))
    return Month(year, month, result)

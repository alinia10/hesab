"""Streamlit UI: upload the monthly PDF, download the Excel. Fully Persian, RTL."""

import tempfile
from pathlib import Path

import streamlit as st

from hesab.excel import MONTHS
from hesab.pipeline import convert

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(x) -> str:
    return str(x).translate(FA_DIGITS)


def hm(minutes: int) -> str:
    return fa(f"{minutes // 60}:{minutes % 60:02d}")


def friendly_error(e: Exception) -> str:
    msg = str(e)
    if "GEMINI_API_KEY" in msg:
        return "کلید Gemini تنظیم نشده است. کلید را در فایل ‎.env‎ با نام GEMINI_API_KEY قرار دهید."
    if "API_KEY_INVALID" in msg or "API key not valid" in msg:
        return "کلید Gemini نامعتبر است. کلید را در فایل ‎.env‎ بررسی کنید."
    if "503" in msg or "UNAVAILABLE" in msg:
        return "سرور Gemini در حال حاضر شلوغ است. چند دقیقه بعد دوباره امتحان کنید."
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return "سهمیه رایگان Gemini موقتاً تمام شده است. چند دقیقه بعد دوباره امتحان کنید."
    if "no dated rows" in msg:
        return "هیچ جدول حضور و غیابی در این فایل پیدا نشد."
    if "input pages" in msg or "MAX_TOKENS" in msg:
        return "پاسخ هوش مصنوعی ناقص بود. لطفاً دوباره امتحان کنید."
    return f"خطا در پردازش فایل: {msg}"


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;700;800&display=swap');

html, body, .stApp, .stApp :not([data-testid="stIconMaterial"]):not(code) {
  font-family: 'Vazirmatn', Tahoma, sans-serif !important;
}
.stApp { direction: rtl; text-align: right; background: #f6f7fb; }
[data-testid="stMainBlockContainer"] { max-width: 760px; padding-top: 2.5rem; }
header[data-testid="stHeader"], [data-testid="stToolbar"], footer { display: none !important; }

.hero {
  background: linear-gradient(135deg, #1f4e79 0%, #2e75b6 100%);
  color: #fff; border-radius: 18px; padding: 28px 30px; margin-bottom: 22px;
  box-shadow: 0 10px 30px rgba(31, 78, 121, .18);
}
.hero h1 { color: #fff !important; font-size: 1.7rem; font-weight: 800; margin: 0 0 6px !important; padding: 0 !important; }
.hero h1 > div, .hero h1 span { margin: 0 !important; padding: 0 !important; }
[data-testid="stHeaderActionElements"], .hero h1 a { display: none !important; }
.hero p { color: #dbe8f5; margin: 0; font-size: 1rem; line-height: 1.9; }

.steps { display: flex; gap: 10px; margin: 0 0 18px; flex-wrap: wrap; }
.step {
  flex: 1 1 150px; background: #fff; border: 1px solid #e3e7ef; border-radius: 12px;
  padding: 12px 14px; font-size: .9rem; color: #44506a;
}
.step b { display: block; color: #1f4e79; font-size: 1.05rem; margin-bottom: 2px; }

/* file uploader: replace built-in English text */
[data-testid="stFileUploader"] label { display: none; }
[data-testid="stFileUploaderDropzone"] {
  direction: rtl; background: #fff; border: 2px dashed #9db8d6; border-radius: 14px; padding: 26px;
}
[data-testid="stFileUploaderDropzoneInstructions"] { display: none !important; }
[data-testid="stFileUploaderDropzone"]::before {
  content: "فایل PDF فرم‌های اسکن‌شده را اینجا رها کنید";
  color: #44506a; font-weight: 500; margin-left: auto;
}
[data-testid="stFileUploaderDropzone"] button { font-size: 0 !important; }
[data-testid="stFileUploaderDropzone"] button * { font-size: 0 !important; }
[data-testid="stFileUploaderDropzone"] button::after {
  content: "انتخاب فایل"; font-size: .95rem; font-weight: 500;
}
[data-testid="stFileUploaderFile"] { direction: rtl; }

[data-testid="stElementContainer"]:has([data-testid="stButton"]),
[data-testid="stElementContainer"]:has([data-testid="stDownloadButton"]),
[data-testid="stButton"], [data-testid="stDownloadButton"],
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button {
  width: 100%; border-radius: 12px; padding: .7rem 1rem; font-weight: 700; font-size: 1.05rem;
}

.cards { display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 0 18px; }
.card {
  flex: 1 1 130px; background: #fff; border: 1px solid #e3e7ef; border-radius: 14px; padding: 14px 16px;
  text-align: center;
}
.card .v { font-size: 1.6rem; font-weight: 800; color: #1f4e79; }
.card .l { font-size: .85rem; color: #6b7690; }
.card.warn .v { color: #b7791f; }

table.people { width: 100%; border-collapse: separate; border-spacing: 0; background: #fff;
  border: 1px solid #e3e7ef; border-radius: 14px; overflow: hidden; margin-bottom: 18px; }
table.people th { background: #dde4ee; color: #1f3550; font-weight: 700; padding: 10px; text-align: right; }
table.people td { padding: 10px; border-top: 1px solid #eef1f6; color: #2b3445; }
table.people td.num { text-align: center; }
.badge { white-space: nowrap; background: #fff2a8; color: #7a5a00; border-radius: 8px; padding: 2px 10px; font-size: .85rem; }
.ok { color: #2e7d32; }

.note { color: #6b7690; font-size: .85rem; line-height: 1.9; margin-top: 8px; }
[data-testid="stAlert"] { direction: rtl; text-align: right; }
</style>
"""

st.set_page_config(page_title="حضور و غیاب به اکسل", page_icon="📊", layout="centered")
st.markdown(CSS, unsafe_allow_html=True)

st.markdown(
    """
<div class="hero">
  <h1>تبدیل فرم حضور و غیاب به اکسل</h1>
  <p>فایل PDF اسکن‌شده‌ی ماه را بدهید و یک فایل اکسل کامل تحویل بگیرید:
  هر نفر در یک برگه، همراه با برگه‌ی خلاصه و محاسبه‌ی خودکار کارکرد روزانه.</p>
</div>
<div class="steps">
  <div class="step"><b>۱. بارگذاری</b>فایل PDF فرم‌ها را انتخاب کنید</div>
  <div class="step"><b>۲. تبدیل</b>صفحات با هوش مصنوعی خوانده می‌شوند</div>
  <div class="step"><b>۳. دریافت</b>فایل اکسل را دانلود و خانه‌های زرد را بررسی کنید</div>
</div>
""",
    unsafe_allow_html=True,
)

uploaded = st.file_uploader("فایل PDF", type="pdf", label_visibility="collapsed")

if uploaded and st.button("تبدیل به اکسل", type="primary"):
    with st.spinner("در حال خواندن همه‌ی صفحات در یک درخواست؛ ممکن است چند دقیقه طول بکشد ..."), \
            tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "input.pdf"
        pdf.write_bytes(uploaded.getvalue())
        try:
            data, month, pages = convert(str(pdf))
        except Exception as e:
            st.error(friendly_error(e))
            st.stop()
    st.session_state.result = (data, month, len(pages), uploaded.name)

if "result" in st.session_state:
    data, month, n_pages, name = st.session_state.result
    flagged_total = sum(1 for p in month.people for d in p.days if d.flags)
    period = f"{MONTHS[month.month - 1]} {fa(month.year or '')}".strip()

    st.markdown(
        f"""
<div class="cards">
  <div class="card"><div class="v">{fa(n_pages)}</div><div class="l">صفحه</div></div>
  <div class="card"><div class="v">{fa(len(month.people))}</div><div class="l">نفر</div></div>
  <div class="card"><div class="v">{period}</div><div class="l">ماه</div></div>
  <div class="card{' warn' if flagged_total else ''}"><div class="v">{fa(flagged_total)}</div>
    <div class="l">ردیف نیازمند بررسی</div></div>
</div>
""",
        unsafe_allow_html=True,
    )

    rows = []
    for p in month.people:
        worked = sum(1 for d in p.days if d.total > 0)
        flagged = sum(1 for d in p.days if d.flags)
        check = f'<span class="badge">{fa(flagged)} ردیف</span>' if flagged else '<span class="ok">✓</span>'
        rows.append(
            f"<tr><td>{p.name}</td><td class='num'>{fa(worked)}</td>"
            f"<td class='num'>{hm(sum(d.total for d in p.days))}</td><td class='num'>{check}</td></tr>"
        )
    st.markdown(
        "<table class='people'><tr><th>نام و نام خانوادگی</th><th>روزهای کاری</th>"
        "<th>جمع ساعت</th><th>بررسی</th></tr>" + "".join(rows) + "</table>",
        unsafe_allow_html=True,
    )

    st.download_button(
        "دانلود فایل اکسل",
        data,
        file_name=Path(name).with_suffix(".xlsx").name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
    st.markdown(
        '<p class="note">خانه‌های <b>زرد</b> در اکسل مقادیری هستند که با اطمینان خوانده نشده‌اند یا با هم '
        "جور درنمی‌آیند؛ آن‌ها را با برگه‌ی اصلی مقایسه کنید. با اصلاح هر ساعت در اکسل، جمع روزانه و ماهانه "
        "خودکار به‌روز می‌شود.</p>",
        unsafe_allow_html=True,
    )

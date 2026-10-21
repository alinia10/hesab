"""Streamlit UI: upload the monthly PDF, download the Excel."""

import tempfile
from pathlib import Path

import streamlit as st

from hesab.pipeline import convert

st.set_page_config(page_title="hesab", page_icon="📊")
st.title("حضور و غیاب → اکسل")

uploaded = st.file_uploader("PDF فرم‌های اسکن‌شده", type="pdf")
if uploaded and st.button("تبدیل", type="primary"):
    bar = st.progress(0.0, text="در حال خواندن صفحات ...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "input.pdf"
        pdf.write_bytes(uploaded.getvalue())
        try:
            data, month, pages = convert(
                str(pdf), progress=lambda i, n: bar.progress(i / n, text=f"صفحه {min(i + 1, n)} از {n}")
            )
        except Exception as e:
            st.error(f"خطا: {e}")
            st.stop()
    bar.empty()
    st.success(f"{len(pages)} صفحه، {len(month.people)} نفر")
    st.table({
        "نام": [p.name for p in month.people],
        "روز کاری": [sum(1 for d in p.days if d.total > 0) for p in month.people],
        "جمع ساعت": [f"{t // 60}:{t % 60:02d}" for t in (sum(d.total for d in p.days) for p in month.people)],
        "ردیف نیازمند بررسی": [sum(1 for d in p.days if d.flags) for p in month.people],
    })
    st.download_button(
        "دانلود اکسل",
        data,
        file_name=Path(uploaded.name).with_suffix(".xlsx").name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

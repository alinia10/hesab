"""Local web UI: one RTL Persian page with a title and an upload box. PDF in -> Excel out."""

import argparse
import json
import tempfile
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote

from .pipeline import convert

MAX_UPLOAD = 100 * 1024 * 1024
LTR = "⁦{}⁩"  # isolate Latin text inside Persian sentences

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def friendly_error(e: Exception) -> str:
    msg = str(e)
    if "GEMINI_API_KEY" in msg:
        return f"کلید Gemini تنظیم نشده است. کلید را در فایل {LTR.format('.env')} قرار دهید."
    if "API_KEY_INVALID" in msg or "API key not valid" in msg:
        return f"کلید Gemini نامعتبر است. کلید را در فایل {LTR.format('.env')} بررسی کنید."
    if "503" in msg or "UNAVAILABLE" in msg:
        return "سرور Gemini در حال حاضر شلوغ است. چند دقیقه بعد دوباره امتحان کنید."
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return "سهمیه رایگان Gemini موقتاً تمام شده است. کمی بعد دوباره امتحان کنید."
    if "no dated rows" in msg:
        return "هیچ جدول حضور و غیابی در این فایل پیدا نشد."
    if "input pages" in msg or "MAX_TOKENS" in msg:
        return "پاسخ هوش مصنوعی ناقص بود. دوباره امتحان کنید."
    return "خطا در تبدیل فایل: " + LTR.format(msg[:300])


def run_job(job_id: str, pdf: bytes) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "input.pdf"
        path.write_bytes(pdf)
        try:
            data, _, _ = convert(str(path))
            result = {"state": "done", "data": data}
        except Exception as e:
            result = {"state": "error", "message": friendly_error(e)}
    with JOBS_LOCK:
        JOBS[job_id].update(result)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # keep the console quiet
        pass

    def send_json(self, obj: dict, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        kind, _, job_id = self.path.strip("/").partition("/")
        with JOBS_LOCK:
            job = dict(JOBS.get(job_id, {}))
        if not job:
            self.send_json({"state": "error", "message": "این درخواست پیدا نشد. فایل را دوباره انتخاب کنید."}, 404)
        elif kind == "status":
            self.send_json({k: v for k, v in job.items() if k in ("state", "message")})
        elif kind == "download" and job["state"] == "done":
            name = Path(job["name"]).stem + ".xlsx"
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f"attachment; filename=\"hesab.xlsx\"; filename*=UTF-8''{quote(name)}")
            self.send_header("Content-Length", str(len(job["data"])))
            self.end_headers()
            self.wfile.write(job["data"])
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/convert":
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length") or 0)
        if not 0 < size <= MAX_UPLOAD:
            self.send_json({"message": "حجم فایل مجاز نیست."}, 400)
            return
        pdf = self.rfile.read(size)
        if not pdf.startswith(b"%PDF"):
            self.send_json({"message": "فقط فایل PDF قابل قبول است."}, 400)
            return
        job_id = uuid.uuid4().hex
        with JOBS_LOCK:
            JOBS[job_id] = {"state": "running", "name": unquote(self.headers.get("X-Filename") or "hesab.pdf")}
        threading.Thread(target=run_job, args=(job_id, pdf), daemon=True).start()
        self.send_json({"id": job_id})


def main() -> None:
    ap = argparse.ArgumentParser(prog="hesab-web", description="Attendance PDF -> Excel, in the browser")
    ap.add_argument("--port", type=int, default=8501)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = ap.parse_args()

    for port in range(args.port, args.port + 20):  # next free port if this one is taken
        try:
            server = ThreadingHTTPServer((args.host, port), Handler)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"no free port from {args.port}")
    server.daemon_threads = True
    url = f"http://localhost:{port}"
    print(f"hesab is running at {url}  (close this window or press Ctrl+C to stop)", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


PAGE = """<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>تبدیل حضور و غیاب به اکسل</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #f3f5f9; --card: #ffffff; --ink: #1d2939; --muted: #667085; --line: #c9d4e3;
    --brand: #1f4e79; --brand-soft: #eaf1f8; --ok: #1e7a46; --err: #b42318;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; min-height: 100%; }
  body {
    font-family: Vazirmatn, Tahoma, sans-serif; background: var(--bg); color: var(--ink);
    min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px 16px;
  }
  main { width: 100%; max-width: 560px; }
  h1 { margin: 0 0 24px; text-align: center; font-size: 1.7rem; font-weight: 800; color: var(--brand); }
  #drop {
    background: var(--card); border: 2px dashed var(--line); border-radius: 20px;
    min-height: 280px; padding: 40px 24px; cursor: pointer; outline: none;
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px;
    text-align: center; transition: border-color .15s, background-color .15s;
  }
  #drop:hover, #drop:focus-visible, #drop.over { border-color: var(--brand); background: var(--brand-soft); }
  #drop.busy { cursor: progress; border-style: solid; background: var(--card); }
  .icon { width: 56px; height: 56px; color: var(--brand); }
  .icon.ok { color: var(--ok); }
  .icon.err { color: var(--err); }
  .label { font-size: 1.1rem; font-weight: 500; }
  .label.err { color: var(--err); line-height: 1.9; }
  .file {
    max-width: 100%; color: var(--muted); font-size: .9rem; direction: ltr; unicode-bidi: isolate;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .clock { color: var(--muted); font-size: .95rem; }
  .spinner {
    width: 48px; height: 48px; border-radius: 50%;
    border: 4px solid var(--brand-soft); border-top-color: var(--brand); animation: spin 1s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .btn {
    font: inherit; font-weight: 700; color: #fff; background: var(--brand); border: 0; border-radius: 12px;
    padding: 12px 32px; text-decoration: none; cursor: pointer;
  }
  .btn:hover { filter: brightness(1.12); }
  .link { font: inherit; font-size: .9rem; color: var(--brand); background: none; border: 0; cursor: pointer; text-decoration: underline; }
</style>
</head>
<body>
<main>
  <h1>تبدیل حضور و غیاب به اکسل</h1>
  <div id="drop" tabindex="0" role="button" aria-label="انتخاب فایل PDF"></div>
  <input id="pick" type="file" accept="application/pdf,.pdf" hidden>
</main>
<script>
const drop = document.getElementById('drop');
const pick = document.getElementById('pick');
const fa = s => String(s).replace(/[0-9]/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
const esc = s => { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; };
const svg = (cls, path) => `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
const ICON_UP = svg('', '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M12 17v-6"/><path d="m9.5 13.5 2.5-2.5 2.5 2.5"/>');
const ICON_OK = svg('ok', '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 2.8 2.8L16.5 9.5"/>');
const ICON_ERR = svg('err', '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5"/><path d="M12 16.5h.01"/>');
let busy = false, timer = null;

function show(html, isBusy) {
  busy = isBusy;
  drop.classList.toggle('busy', isBusy);
  drop.innerHTML = html;
}
function idle() {
  show(`${ICON_UP}<div class="label">فایل PDF را اینجا بکشید یا کلیک کنید</div>`, false);
}
function fail(message, name) {
  clearInterval(timer);
  show(`${ICON_ERR}<div class="label err">${esc(message)}</div>` +
       (name ? `<div class="file">${esc(name)}</div>` : '') +
       `<button class="link" type="button">انتخاب دوباره</button>`, false);
}
function done(id, name) {
  clearInterval(timer);
  const xlsx = name.replace(/\\.pdf$/i, '') + '.xlsx';
  const url = '/download/' + id;
  show(`${ICON_OK}<div class="label">فایل اکسل آماده است</div><div class="file">${esc(xlsx)}</div>` +
       `<a class="btn" href="${url}" download>دانلود اکسل</a>` +
       `<button class="link" type="button" data-again>تبدیل فایل دیگر</button>`, false);
  drop.querySelector('a').click();
}

class AppError extends Error {}
async function start(file) {
  if (!/\\.pdf$/i.test(file.name) && file.type !== 'application/pdf') return fail('فقط فایل PDF قابل قبول است.', file.name);
  const t0 = Date.now();
  show(`<div class="spinner"></div><div class="label">در حال تبدیل ...</div>` +
       `<div class="file">${esc(file.name)}</div><div class="clock" id="clock">۰:۰۰</div>`, true);
  timer = setInterval(() => {
    const s = Math.floor((Date.now() - t0) / 1000);
    document.getElementById('clock').textContent = fa(Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'));
  }, 1000);
  try {
    const r = await fetch('/convert', { method: 'POST', headers: { 'X-Filename': encodeURIComponent(file.name) }, body: file });
    const job = await r.json();
    if (!r.ok) throw new AppError(job.message);
    for (;;) {
      await new Promise(res => setTimeout(res, 2000));
      const st = await (await fetch('/status/' + job.id, { cache: 'no-store' })).json();
      if (st.state === 'done') return done(job.id, file.name);
      if (st.state === 'error') throw new AppError(st.message);
    }
  } catch (e) {
    fail(e instanceof AppError ? e.message : 'ارتباط با برنامه قطع شد. پنجره‌ی برنامه را دوباره باز کنید.', file.name);
  }
}

drop.addEventListener('click', e => {
  if (busy || e.target.closest('a')) return;
  if (e.target.closest('[data-again]')) return idle();
  pick.click();
});
drop.addEventListener('keydown', e => {
  if (!busy && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); pick.click(); }
});
['dragenter', 'dragover'].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); if (!busy) drop.classList.add('over'); }));
['dragleave', 'drop'].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', e => { if (!busy && e.dataTransfer.files.length) start(e.dataTransfer.files[0]); });
pick.addEventListener('change', () => { if (pick.files.length) start(pick.files[0]); pick.value = ''; });
window.addEventListener('dragover', e => e.preventDefault());
window.addEventListener('drop', e => e.preventDefault());
idle();
</script>
</body>
</html>
"""

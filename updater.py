"""التحديث من داخل التطبيق: يقرأ version.json، ينزّل الحزمة، يتحقق من بصمتها SHA-256، ثم يسلّم التركيب لـ update_apply.py.

شكل version.json:
    {"version": "1.1.0", "zip_url": "https://.../AsobiTranslator-1.1.0.zip", "sha256": "<hex>", "notes": "..."}
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from version import UPDATE_URL, VERSION

BASE = Path(__file__).resolve().parent
STAGE = BASE / "update_stage"
MAX_ZIP = 200 * 1024 * 1024
UA = {"User-Agent": "AsobiTranslator-Updater"}


def parse(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4]) or (0,)


def _url():
    return os.environ.get("ASOBI_UPDATE_URL") or UPDATE_URL


def _safe(url):
    """https فقط (و http للجهاز المحلي للاختبار)."""
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" or (p.scheme == "http" and p.hostname in ("localhost", "127.0.0.1"))


def check():
    """يرجع (manifest أو None, رسالة). manifest فيه 'version' الأحدث فقط لو أحدث من الحالية."""
    url = _url()
    if not url:
        return None, "ما في رابط تحديثات بعد"
    if not _safe(url):
        return None, "رابط التحديثات لازم يكون https"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            m = json.loads(r.read(1_000_000).decode("utf-8"))
        for k in ("version", "zip_url", "sha256"):
            if k not in m:
                return None, "ملف التحديثات ناقص"
    except Exception as e:
        return None, f"تعذر الاتصال بخادم التحديثات ({type(e).__name__})"
    try:  # تحديث فشل قبل (تراجع تلقائي): ما نكرره في كل تشغيل
        if (BASE / "update_failed.txt").read_text(encoding="utf-8").strip() == str(m["version"]):
            return None, "هذا التحديث فشل سابقاً وتم التراجع عنه"
    except OSError:
        pass
    if parse(m["version"]) > parse(VERSION):
        return m, f"يتوفر إصدار جديد {m['version']}"
    return None, "أنت على آخر إصدار ✓"


def download(m, progress=None):
    """ينزّل الحزمة ويتحقق ويفكها في update_stage. يرمي استثناء عند أي خلل."""
    if not _safe(m["zip_url"]):
        raise RuntimeError("رابط الحزمة لازم يكون https")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir()
    zp = STAGE / "pkg.zip"
    h = hashlib.sha256()
    req = urllib.request.Request(m["zip_url"], headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r, open(zp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            b = r.read(256 * 1024)
            if not b:
                break
            done += len(b)
            if done > MAX_ZIP:
                raise RuntimeError("الحزمة أكبر من المسموح")
            h.update(b)
            f.write(b)
            if progress and total:
                progress(done / total)
    if h.hexdigest().lower() != str(m["sha256"]).lower():
        shutil.rmtree(STAGE, ignore_errors=True)
        raise RuntimeError("بصمة الحزمة ما تطابق: التحديث ملغي")
    out = STAGE / "files"
    with zipfile.ZipFile(zp) as z:
        for n in z.namelist():
            dest = (out / n).resolve()
            if out.resolve() not in dest.parents and dest != out.resolve():
                raise RuntimeError("حزمة غير آمنة")
        z.extractall(out)
    if not (out / "app.py").exists():
        raise RuntimeError("الحزمة ما فيها app.py")
    zp.unlink()
    return out


def write_ready(version):
    """يعلّم الحزمة المنزّلة (والمتحقق منها) أنها جاهزة للتركيب."""
    (STAGE / "ready.json").write_text(json.dumps({"version": str(version)}), encoding="utf-8")


def staged():
    """(مجلد الملفات, الإصدار) لو في تحديث جاهز ومنزّل قبل وأحدث من الحالي، وإلا None."""
    try:
        v = json.loads((STAGE / "ready.json").read_text(encoding="utf-8"))["version"]
        files = STAGE / "files"
        if parse(v) > parse(VERSION) and (files / "app.py").exists():
            return files, v
    except Exception:
        pass
    shutil.rmtree(STAGE, ignore_errors=True)  # قديم أو تالف
    return None


def apply_and_exit(files_dir, new_version):
    """يشغّل المحدّث بعملية مستقلة، وبعدها التطبيق يقفل نفسه."""
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pyw if pyw.exists() else sys.executable)
    flags = 0x08000000 | 0x00000008 | 0x00000200  # بدون نافذة، منفصلة عن التطبيق
    subprocess.Popen([exe, "-I", str(BASE / "update_apply.py"), str(os.getpid()), str(files_dir), str(BASE),
                      str(new_version)], creationflags=flags, close_fds=True, cwd=str(BASE))
    os._exit(0)

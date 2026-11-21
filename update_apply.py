"""يركّب التحديث بعد ما يقفل التطبيق: نسخ احتياطي، نسخ الملفات الجديدة، pip لو تغيّرت المتطلبات، ثم إعادة التشغيل.
config.json لا يُستبدل أبداً، وglossary.json لا يُستبدل إذا موجود (تعديلاتك محفوظة)."""
import ctypes
import shutil
import subprocess
import sys
import time
from pathlib import Path

KEEP = {"config.json", "glossary.json"}
ALLOWED = {".py", ".json", ".txt", ".md", ".bat", ".ico", ".png", ".ps1"}


def alive(pid):
    h = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not h:
        return False
    r = ctypes.windll.kernel32.WaitForSingleObject(h, 0)
    ctypes.windll.kernel32.CloseHandle(h)
    return r == 0x102


def main():
    pid, src, app, ver = int(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
    log = open(app / "update.log", "a", encoding="utf-8", buffering=1)

    def say(*a):
        print(time.strftime("%H:%M:%S"), *a, file=log, flush=True)

    for _ in range(100):  # ننتظر التطبيق يقفل (حد أقصى 20 ثانية)
        if not alive(pid):
            break
        time.sleep(0.2)
    say("تحديث إلى", ver)
    backup = app / "backup"
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    backup.mkdir()
    changed = []
    try:
        old_req = (app / "requirements.txt").read_text(encoding="utf-8") if (app / "requirements.txt").exists() else ""
        for f in sorted(p for p in src.rglob("*") if p.is_file()):
            rel = f.relative_to(src)
            if f.suffix.lower() not in ALLOWED or (rel.name in KEEP and (app / rel).exists()):
                continue
            dst = app / rel
            if dst.exists():
                (backup / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, backup / rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            changed.append((rel, dst.exists()))
            shutil.copy2(f, dst)
        new_req = (app / "requirements.txt").read_text(encoding="utf-8") if (app / "requirements.txt").exists() else ""
        py = app / ".venv" / "Scripts" / "python.exe"
        if new_req != old_req and py.exists():
            say("تغيّرت المتطلبات: pip install")
            r = subprocess.run([str(py), "-m", "pip", "install", "-r", str(app / "requirements.txt")],
                               creationflags=0x08000000, capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError("pip فشل: " + r.stdout[-400:] + r.stderr[-400:])
        say("تم")
    except Exception as e:
        say("فشل التحديث، رجوع للنسخة السابقة:", repr(e))
        for rel, existed in changed:
            if (backup / rel).exists():
                shutil.copy2(backup / rel, app / rel)
            elif not existed:
                (app / rel).unlink(missing_ok=True)
    shutil.rmtree(src.parent, ignore_errors=True)
    pyw = app / ".venv" / "Scripts" / "pythonw.exe"
    subprocess.Popen([str(pyw if pyw.exists() else sys.executable), str(app / "app.py")], cwd=str(app),
                     creationflags=0x08000000 | 0x00000008 | 0x00000200, close_fds=True)


if __name__ == "__main__":
    main()

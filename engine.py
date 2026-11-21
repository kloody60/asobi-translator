"""محرك مترجم Asobi: قراءة الشاشة (OCR) + صوت اللعبة (Whisper) + الترجمة للعربية (NLLB).
الإعدادات حيّة: الواجهة (app.py) تعدّل CFG وهالمحرك يقراها كل دورة بدون إعادة تشغيل."""
import copy
import ctypes
import ctypes.wintypes as wt
import json
import os
import queue
import re
import sys
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path

import numpy as np
import torch  # لازم يتحمّل قبل ctranslate2 عشان يستخدم نفس نسخة cuDNN

BASE = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("ASOBI_CONFIG", BASE / "config.json"))

DEFAULTS = {
    "window_title_contains": "Asobi",
    "window_exe": "asobideck.exe",
    "auto_start": False,
    "update": {"auto_check": True},
    "ui": {"advanced": False},
    "target_language": "arb_Arab",
    "translation_model_dir": "models/nllb-3.3B-ct2",
    "performance": {"profile": "auto", "device": "auto", "cpu_threads": 8, "ocr_max_fps": 4, "gpu_memory_fraction": 0.6},
    "screen": {
        "enabled": True, "reader_groups": [["en"], ["ja", "en"]],
        "region": [0.05, 0.62, 0.95, 0.98], "min_confidence": 0.5, "min_letters": 4,
        "change_threshold": 4.0, "stable_reads": 2, "hide_after_seconds": 6,
    },
    "audio": {
        "enabled": True, "source": "app", "device": "auto", "language": "auto", "show_arabic": False,
        "high_accuracy": True, "hint_words": "", "live": True, "display_mode": "translate", "save_history": True, "live_interval": 0.4, "live_tentative": True,
        "whisper_model": "large-v3",
        "vad_threshold": 0.45, "boost_quiet": True, "silence_seconds": 0.5,
        "max_utterance_seconds": 8, "hide_after_seconds": 7,
    },
    "overlay": {
        "enabled": True, "visible_in_capture": True, "obs_window": False, "show_original": False,
        "font": "Segoe UI", "font_size": 28,
        "text_color": "#FFFFFF", "text_opacity": 100, "bg_color": "#000000", "bg_opacity": 82,
        "radius": 12, "pad_y": 10, "pos_x": 0.5, "pos_y": 0.9, "width": 0.8,
    },
}


def _merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _merge(dst[k], v)
        else:
            dst[k] = v


CFG = copy.deepcopy(DEFAULTS)
if CONFIG_PATH.exists():
    _merge(CFG, json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
GLOSS = json.loads((BASE / "glossary.json").read_text(encoding="utf-8")).get("lines", {})
_save_lock = threading.Lock()


def save_config():
    with _save_lock:
        CONFIG_PATH.write_text(json.dumps(CFG, ensure_ascii=False, indent=2), encoding="utf-8")


# تشغيل/إيقاف الترجمة (زر ابدأ في الواجهة). النماذج تتحمّل من أول البرنامج عشان البدء يكون فوري
RUN = {"on": False}
# حالة تعرضها الواجهة
STATE = {"translation": "لم يبدأ", "ocr": "لم يبدأ", "audio": "لم يبدأ", "heard": ""}

NLLB = {
    "en": "eng_Latn", "ja": "jpn_Jpan", "ko": "kor_Hang", "zh": "zho_Hans", "fr": "fra_Latn",
    "de": "deu_Latn", "es": "spa_Latn", "it": "ita_Latn", "pt": "por_Latn", "ru": "rus_Cyrl",
    "tr": "tur_Latn", "pl": "pol_Latn", "nl": "nld_Latn", "uk": "ukr_Cyrl",
}
user32 = ctypes.windll.user32


# ---------- نافذة Asobi ----------
kernel32 = ctypes.windll.kernel32
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
kernel32.CloseHandle.argtypes = [wt.HANDLE]


def _exe_ok(pid):
    """النافذة لازم تكون لعملية Asobi فعلاً (مو أي نافذة فيها كلمة Asobi بعنوانها، مثل Terminal أو متصفح)."""
    want = str(CFG.get("window_exe", "asobideck.exe")).lower()
    if not want:
        return True
    h = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        buf, n = ctypes.create_unicode_buffer(520), wt.DWORD(520)
        return bool(kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))) \
            and os.path.basename(buf.value).lower() == want
    finally:
        kernel32.CloseHandle(h)


gdi32 = ctypes.windll.gdi32
user32.GetWindowDC.restype = wt.HDC
user32.GetWindowDC.argtypes = [wt.HWND]
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]
gdi32.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]


class _BMIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


def grab_client(hwnd, w, h):
    """يصوّر محتوى نافذة Asobi نفسها (BGR). النوافذ الطافية فوقها (مثل الترجمة) ما تظهر فيه، فالقارئ ما يقرا
    الترجمة حتى لو كانت ظاهرة للبث. يرجع None إذا فشل."""
    sdc = user32.GetWindowDC(hwnd)
    if not sdc:
        return None
    mdc = gdi32.CreateCompatibleDC(sdc)
    bmp = gdi32.CreateCompatibleBitmap(sdc, w, h)
    try:
        gdi32.SelectObject(mdc, bmp)
        if not user32.PrintWindow(hwnd, mdc, 3):  # PW_CLIENTONLY | PW_RENDERFULLCONTENT
            return None
        bi = _BMIH(ctypes.sizeof(_BMIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
        return np.frombuffer(buf, np.uint8).reshape(h, w, 4)[:, :, :3].copy()
    finally:
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(hwnd, sdc)


def find_window():
    """يرجع (hwnd, left, top, right, bottom) للمنطقة الداخلية لنافذة Asobi، أو None."""
    needle = CFG["window_title_contains"].lower()
    me = os.getpid()
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if needle in buf.value.lower():
                    pid = wt.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value != me and _exe_ok(pid.value):  # لا نلقط نوافذ برنامجنا ولا نوافذ غير Asobi
                        found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    for hwnd in found:
        rc = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rc))
        pt = wt.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        w, h = rc.right - rc.left, rc.bottom - rc.top
        if w > 200 and h > 200:
            return hwnd, pt.x, pt.y, pt.x + w, pt.y + h
    return None


# ---------- الترجمة ----------
_prof = {}


def active_profile():
    """ملف الأداء المستخدم (حسب الكرت أو اختيار المستخدم). يُحسب مرة وحدة لكل تشغيل."""
    if not _prof:
        import profiles
        name, note = profiles.resolve(CFG["performance"].get("profile", "auto"), BASE)
        gpu, vram = profiles.gpu_info()
        _prof.update(profiles.PROFILES[name], name=name, note=note, gpu=gpu, vram=vram,
                     use_gpu=name != "cpu" and CFG["performance"]["device"] in ("auto", "cuda") and gpu is not None)
        STATE["profile"] = f"{profiles.PROFILES[name]['label']}" + (f" — {gpu} ({vram:.0f} GB)" if gpu else " — بدون كرت NVIDIA")
        print(f"[أداء] {STATE['profile']} | {note}", flush=True)
    return _prof


def _first_ok(make, types):
    """يجرّب أنواع الدقة بالترتيب (بعض الكروت القديمة ما تدعم int8_float16)."""
    err = None
    for t in types:
        try:
            return make(t), t
        except Exception as e:
            err = e
            print(f"[أداء] الدقة {t} غير مدعومة: {e}", flush=True)
    raise err


class Translator:
    def __init__(self):
        import ctranslate2
        from transformers import AutoTokenizer

        perf = CFG["performance"]
        pf = active_profile()
        gpu = pf["use_gpu"] and ctranslate2.get_cuda_device_count() > 0
        self.device = "cuda" if gpu else "cpu"
        model_dir = BASE / "models" / pf["nllb"]
        if not (model_dir / "model.bin").exists():
            raise FileNotFoundError(f"نموذج الترجمة غير موجود: {model_dir} — شغّل المثبّت أو prepare_models.py")
        self.tok = AutoTokenizer.from_pretrained(str(model_dir))
        types = [pf["nc"], "int8", "float16"] if gpu else ["int8"]
        self.tr, ct = _first_ok(lambda t: ctranslate2.Translator(
            str(model_dir), device=self.device, compute_type=t, inter_threads=1, intra_threads=perf["cpu_threads"]), types)
        self.cache = OrderedDict()
        self.lock = threading.Lock()
        self.translate("Hello there, how are you?", "en")  # تسخين
        self.translate("Hello there, how are you?", "en", fast=True)
        print(f"[ترجمة] الجهاز: {self.device} ({ct}) | {pf['nllb']}", flush=True)

    def translate(self, text, lang="en", fast=False):
        """fast=True: بحث مباشر بدون beam (أسرع تقريباً الضعف) للترجمة المبدئية أثناء الكلام."""
        key = " ".join(text.lower().split())
        if key in GLOSS:
            return GLOSS[key]
        ck = (lang, text, fast)
        with self.lock:
            if ck in self.cache:
                self.cache.move_to_end(ck)
                return self.cache[ck]
            self.tok.src_lang = NLLB.get(lang, "eng_Latn")
            # كل سطر وكل جملة لحالها: النموذج يخرّب الأوامر القصيرة لو ترجمها مع جمل ثانية
            parts, line_of = [], []
            for i, line in enumerate(text.split("\n")):
                for p in re.split(r"(?<=[.!?。！？…])\s*", line):
                    if p.strip():
                        parts.append(p)
                        line_of.append(i)
            if not parts:
                return ""
            batch = [self.tok.convert_ids_to_tokens(self.tok(p)["input_ids"]) for p in parts]
            res = self.tr.translate_batch(
                batch, target_prefix=[[CFG["target_language"]]] * len(batch),
                beam_size=1 if fast else 5, max_decoding_length=256, repetition_penalty=1.1)
            outs = [self.tok.decode(self.tok.convert_tokens_to_ids(r.hypotheses[0][1:])) for r in res]
            rows = {}
            for i, o in zip(line_of, outs):
                rows.setdefault(i, []).append(o)
            ar = "\n".join(squash(" ".join(v)) for _, v in sorted(rows.items()))
            self.cache[ck] = ar
            if len(self.cache) > 2000:
                self.cache.popitem(last=False)
            return ar


# ---------- الشاشة: OCR ----------
def join_lines(boxes):
    """يرتّب الكلمات في أسطر (من فوق لتحت، ومن اليسار لليمين داخل السطر)."""
    def yc(b):
        return (b[0][0][1] + b[0][2][1]) / 2
    lines, cur = [], []
    for b in sorted(boxes, key=yc):
        h = b[0][2][1] - b[0][0][1]
        if cur and abs(yc(b) - yc(cur[-1])) > 0.6 * h:
            lines.append(cur)
            cur = []
        cur.append(b)
    if cur:
        lines.append(cur)
    return "\n".join(" ".join(b[1] for b in sorted(ln, key=lambda b: b[0][0][0])) for ln in lines)


def vision_worker(mt, emit, stop):
    import cv2
    import easyocr
    import mss

    sc, perf = CFG["screen"], CFG["performance"]
    use_gpu = perf["device"] in ("auto", "cuda") and torch.cuda.is_available()
    if use_gpu:
        torch.cuda.set_per_process_memory_fraction(perf["gpu_memory_fraction"])
    torch.set_num_threads(perf["cpu_threads"])
    STATE["ocr"] = "جاري التحميل..."
    # قارئ مستقل لكل مجموعة لغات: خلط الإنجليزي والياباني في قارئ واحد يخرّب الحروف اللاتينية
    readers = [easyocr.Reader(g, gpu=use_gpu) for g in sc["reader_groups"]]

    def ocr(img):
        best = ("", 0.0)
        for rd in readers:
            boxes = [b for b in rd.readtext(img) if b[2] >= sc["min_confidence"]]
            if not boxes:
                continue
            text = join_lines(boxes)
            conf = sum(b[2] for b in boxes) / len(boxes)
            if conf >= 0.75:
                return text
            if conf > best[1]:
                best = (text, conf)
        return best[0]

    print(f"[OCR] جاهز، GPU={use_gpu}", flush=True)
    last_sig, cand, cand_n, shown = None, "", 0, ""
    with mss.mss() as grabber:
        while not stop.is_set():
            t0 = time.time()
            delay = 1.0 / max(1, perf["ocr_max_fps"])
            win = find_window()
            if not (RUN["on"] and sc["enabled"]) or not win:
                STATE["ocr"] = ("جاهز — اضغط «ابدأ الترجمة»" if not RUN["on"]
                                else "متوقف" if not sc["enabled"] else "Asobi غير مفتوح")
                last_sig = None
                time.sleep(0.5)
                continue
            STATE["ocr"] = "يقرأ الشاشة"
            hwnd, l, t, r, b = win
            x0, y0, x1, y1 = sc["region"]
            w, h = r - l, b - t
            full = grab_client(hwnd, w, h)
            if full is None or full.std() < 1.0:  # تصوير النافذة فشل أو طلع أسود (مثلاً ملء شاشة حصري): نرجع للشاشة
                full = np.array(grabber.grab({"left": l, "top": t, "width": w, "height": h}))[:, :, :3]
            img = full[int(h * y0):max(int(h * y1), int(h * y0) + 20), int(w * x0):max(int(w * x1), int(w * x0) + 20)]
            sig = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (64, 16)).astype(np.float32)
            unchanged = last_sig is not None and float(np.abs(sig - last_sig).mean()) < sc["change_threshold"]
            if unchanged and not (cand and cand != shown):
                time.sleep(max(0, delay - (time.time() - t0)))
                continue
            last_sig = sig
            if unchanged:
                text, cand_n = cand, sc["stable_reads"]  # الصورة ثابتة = تأكيد القراءة السابقة
            else:
                text = ocr(img).strip()
            if sum(c.isalpha() for c in text) < sc["min_letters"]:
                if shown:
                    emit("", 0)
                    shown = ""
                cand, cand_n = "", 0
            else:
                if not unchanged:
                    cand_n = cand_n + 1 if text == cand else 1
                cand = text
                if cand_n >= sc["stable_reads"] and text != shown:
                    shown = text
                    lang = "ja" if any("぀" <= c <= "ヿ" or "一" <= c <= "鿿" for c in text) else "en"
                    tr = mt.translate(text, lang)
                    emit(tr + ("\x1e" + text.replace("\n", " ") if CFG["overlay"].get("show_original") else ""),
                         sc["hide_after_seconds"])
            time.sleep(max(0, delay - (time.time() - t0)))


# ---------- الصوت: Whisper ----------
_whisper = None
_whisper_lock = threading.Lock()
JUNK = ("thanks for watching", "thank you for watching", "please subscribe", "amara.org")


def get_whisper():
    global _whisper
    with _whisper_lock:
        if _whisper is None:
            from faster_whisper import WhisperModel
            perf = CFG["performance"]
            pf = active_profile()
            gpu = pf["use_gpu"] and torch.cuda.is_available()
            types = [pf["wc"], "int8_float16", "int8"] if gpu else ["int8"]
            _whisper, wt_ = _first_ok(lambda t: WhisperModel(
                pf["whisper"], device="cuda" if gpu else "cpu", compute_type=t, cpu_threads=perf["cpu_threads"]), types)
            print(f"[سماع] {pf['whisper']} ({wt_})", flush=True)
            # تسخين: أول قراءة على الكرت تاخذ ثانيتين، نسويها من الحين عشان أول جملة ما تتأخر
            rng = np.random.RandomState(0)
            for kw in (dict(word_timestamps=True), dict(word_timestamps=False)):
                list(_whisper.transcribe((rng.randn(48000) * 0.02).astype(np.float32), beam_size=1, language="en",
                                         vad_filter=False, temperature=0.0, **kw)[0])
        return _whisper


def list_loopbacks():
    import pyaudiowpatch as pa
    p = pa.PyAudio()
    try:
        return [d["name"] for d in p.get_loopback_device_info_generator()]
    finally:
        p.terminate()


def boost(a, target=0.06, max_gain=12.0):
    """يقوّي الصوت الهادي (حوار اللعبة غالباً هادي) قبل VAD وWhisper."""
    rms = float(np.sqrt(np.mean(a ** 2))) + 1e-9
    if rms >= target:
        return a
    return np.clip(a * min(target / rms, max_gain), -1.0, 1.0).astype(np.float32)


def asobi_pid():
    w = find_window()
    if not w:
        return None
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(w[0], ctypes.byref(pid))
    return pid.value


def open_audio_source(au, stop, q):
    """يفتح مصدر الصوت ويرجع (rate, close, pid) أو None إذا Asobi مو مفتوح.
    source=app: صوت Asobi فقط (بدون Discord والمتصفح) عبر proc-tap. source=system: كل أصوات الجهاز."""
    if au["source"] == "app":
        try:
            from proctap import ProcessAudioCapture
        except ImportError:
            print("[صوت] حزمة proc-tap غير مثبتة: أرجع لالتقاط كل أصوات الجهاز", flush=True)
        else:
            pid = asobi_pid()
            if pid is None:
                return None

            def on_data(data, _n):
                a = np.frombuffer(data, dtype=np.float32)
                q.put(a[:len(a) // 2 * 2].reshape(-1, 2).mean(axis=1))

            cap = ProcessAudioCapture(pid, on_data=on_data)
            cap.start()
            print(f"[صوت] التقاط صوت Asobi فقط (pid {pid})", flush=True)
            return 48000, cap.stop, pid
    import pyaudiowpatch as pa
    p = pa.PyAudio()
    dev = None
    if au["device"] != "auto":
        dev = next((d for d in p.get_loopback_device_info_generator() if d["name"] == au["device"]), None)
    dev = dev or p.get_default_wasapi_loopback()
    rate, ch = int(dev["defaultSampleRate"]), int(dev["maxInputChannels"])
    print(f"[صوت] التقاط كل أصوات الجهاز من: {dev['name']} ({rate}Hz)", flush=True)
    stream = p.open(format=pa.paFloat32, channels=ch, rate=rate, input=True,
                    input_device_index=dev["index"], frames_per_buffer=int(rate * 0.03))
    done = threading.Event()

    def reader():
        # نقرا اللي متوفر فقط: القراءة العادية تتجمّد لو اللعبة ساكتة تماماً وما نقدر نوقف الخيط
        while not done.is_set() and not stop.is_set():
            try:
                n = stream.get_read_available()
                if n > 0:
                    d = np.frombuffer(stream.read(n, exception_on_overflow=False), dtype=np.float32)
                    q.put(d.reshape(-1, ch).mean(axis=1))
                else:
                    time.sleep(0.02)
            except Exception:
                time.sleep(0.05)

    threading.Thread(target=reader, daemon=True).start()

    def close():
        done.set()
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        p.terminate()

    return rate, close, None


def log_history(lang, text, tr):
    """سجل الحوار: كل جملة سمعها (ومعها ترجمتها لو انترجمت) في transcript.log."""
    if not CFG["audio"].get("save_history"):
        return
    try:
        f = BASE / "transcript.log"
        if f.exists() and f.stat().st_size > 2 * 1024 * 1024:
            f.replace(BASE / "transcript.old.log")
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{lang}] {text}" + (f"  =>  {tr}" if tr else "") + "\n")
    except OSError:
        pass


def _norm(w):
    return re.sub(r"[^\w]", "", w.lower())


def looping(text):
    """هلوسة تكرار: نفس الكلمة 5 مرات متتالية فأكثر، أو عبارة تتكرر 3 مرات فأكثر."""
    ws = [_norm(w) for w in text.split()]
    ws = [w for w in ws if w]
    run = 1
    for a, b in zip(ws, ws[1:]):
        run = run + 1 if a == b else 1
        if run >= 5:
            return True
    for n in range(2, 7):
        for i in range(0, len(ws) - 3 * n + 1):
            if ws[i:i + n] == ws[i + n:i + 2 * n] == ws[i + 2 * n:i + 3 * n]:
                return True
    return False


def squash(text):
    """يقصّ التكرار الزائد (عبارة تتكرر مرتين فأكثر تصير مرة وحدة)."""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"(\S.{5,}?)(?:[\s,.،!؟?]+\1)+(?=\W|$)", r"\1", text)
    return text


def audio_worker(mt, emit, stop):
    """سماع صوت اللعبة وترجمته فورياً: يقرا الكلمات أثناء الكلام، ولا يثبّت كلمة إلا إذا ظهرت بنفس الشكل في
    قراءتين متتاليتين (التأكيد المحلي)، يضيفها للجملة ويترجمها. وبعد كل وقفة تدقيق نهائي أدق على الجملة."""
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    from scipy.signal import resample_poly

    au, ov = CFG["audio"], CFG["overlay"]
    STATE["audio"] = "جاري التحميل..."
    model = get_whisper()
    SR = 16000
    q = queue.Queue()
    src = None
    while not stop.is_set():
        src = open_audio_source(au, stop, q)
        if src:
            break
        STATE["audio"] = "Asobi غير مفتوح"
        time.sleep(1)
    if not src:
        return
    rate, close, pid = src

    raw = np.zeros(0, np.float32)
    last_data = last_chk = last_tick = time.time()
    locked, n_seg, hist = None, 0, deque(maxlen=6)
    words_c, prev_tail, commit_abs = [], [], 0.0  # كلمات الجملة المؤكدة، وآخر قراءة بعدها، ونهاية آخر كلمة مؤكدة
    prev_tr, prev_tr_t = "", 0.0                   # سطور الجمل السابقة المعروضة فوق الجملة الحالية
    last_disp = ""                                 # آخر نص مبدئي انعرض (عشان ما نعيد ترجمة نفس النص)

    def vad_opts():
        return VadOptions(threshold=au["vad_threshold"], min_silence_duration_ms=int(au["silence_seconds"] * 1000),
                          speech_pad_ms=150)

    def asr(audio, beam, words=False, prompt="", fallback=True):
        """يفرّغ الصوت لنص. يرجع (segs, info) بعد فلترة الهلوسة، ويحدّث قفل اللغة."""
        nonlocal locked, n_seg
        auto = au["language"] == "auto"
        n_seg += 1
        # قفل اللغة: التعرف التلقائي على جملة قصيرة يغلط (مرة طلعت إنجليزية "برتغالية")، فنثبّت اللغة السائدة
        l = au["language"] if not auto else (None if locked is None or n_seg % 8 == 0 else locked)
        ip = " ".join(x for x in (au["hint_words"].strip(), prompt) if x) or None

        def run(l_):
            ss, inf = model.transcribe(
                audio, beam_size=beam, best_of=1 if beam <= 2 else 5, language=l_, vad_filter=True,
                vad_parameters=vad_opts(), condition_on_previous_text=False, no_speech_threshold=0.5,
                initial_prompt=ip, word_timestamps=words, temperature=(0.0, 0.2, 0.4) if fallback else 0.0)
            return list(ss), inf

        segs, info = run(l)
        if auto and l is None:
            if locked and info.language != locked and info.language_probability < 0.75:
                segs, info = run(locked)  # الكشف مو واثق: نرجع للغة المقفولة
            else:
                det = info.language if info.language_probability > 0.75 else None
                hist.append(det)
                last = list(hist)
                if det and last[-3:] == [det] * 3 or (det and locked and last[-2:] == [det] * 2):
                    locked = det
        # نتجاهل المقاطع المشكوك فيها (هلوسة Whisper على الموسيقى والمؤثرات)
        segs = [s for s in segs if s.avg_logprob > -1.5 and not (s.no_speech_prob > 0.6 and s.avg_logprob < -0.8)
                and not looping(s.text)]
        return segs, info

    def junk(t):
        return not t or any(j in t.lower() for j in JUNK)

    def keep_line():
        return prev_tr if prev_tr and time.time() - prev_tr_t < 6 else ""

    def mode():  # translate = ترجمة | original = الكلام الأصلي بدون ترجمة | both = الاثنين
        return au.get("display_mode", "translate")

    def pack(tr, orig):  # النص الأصلي بعد فاصل خاص، النافذة تعرضه فوق الترجمة في وضع «الاثنين»
        return f"{tr}\x1e{orig}" if mode() == "both" else tr

    def show(tr, orig):
        k = keep_line()
        lines = ((k + "\n" + tr) if k else tr).split("\n")[-2:]  # سطرين كحد أقصى
        emit(pack("\n".join(lines), orig), au["hide_after_seconds"])

    def finish_sentence(text, lang):
        """جملة كاملة: ترجمة دقيقة (beam) وتنزل فوق الجملة اللي بعدها."""
        nonlocal prev_tr, prev_tr_t
        STATE["heard"] = text
        print(f"[سمعت:{lang}]", text, flush=True)
        tr = text if mode() == "original" else mt.translate(text, lang)
        log_history(lang, text, "" if mode() == "original" else tr)
        k = keep_line()
        shown = "\n".join(((k + "\n" + tr) if k else tr).split("\n")[-2:])  # سطرين كحد أقصى
        prev_tr = shown
        prev_tr_t = time.time()
        emit(pack(shown, text), au["hide_after_seconds"])

    try:
        while not stop.is_set():
            time.sleep(0.1)
            if pid is not None and time.time() - last_chk > 3:
                last_chk = time.time()
                if asobi_pid() != pid:  # Asobi انقفل أو انفتح من جديد: نعيد الالتقاط
                    print("[صوت] تغيّر Asobi، إعادة الالتقاط", flush=True)
                    return
            if not (RUN["on"] and au["enabled"]):
                STATE["audio"] = "متوقف" if RUN["on"] else "جاهز — اضغط «ابدأ الترجمة»"
                while not q.empty():
                    q.get()
                raw = np.zeros(0, np.float32)
                words_c, prev_tail, commit_abs = [], [], 0.0
                continue
            STATE["audio"] = "يسمع"
            got = False
            while not q.empty():
                raw = np.concatenate([raw, q.get()])
                got = True
            if got:
                last_data = time.time()
            now = time.time()
            if len(raw) < rate * 0.5:
                continue
            live_due = au["live"] and now - last_tick >= au["live_interval"]
            # بدون وضع فوري نفحص كل 0.4 ثانية بس، ومع الفوري كل فترة التحديث
            if now - last_tick < (au["live_interval"] if au["live"] else 0.4):
                continue
            last_tick = now
            a16 = resample_poly(raw, SR, rate).astype(np.float32)
            if au["boost_quiet"]:
                a16 = boost(a16)
            dur = len(a16) / SR
            sp = get_speech_timestamps(a16, vad_opts())
            if not sp:
                words_c, prev_tail, commit_abs = [], [], 0.0
                if dur > 2.0:
                    raw = raw[-int(rate * 1.0):]  # نترك ثانية من الخلف عشان ما يضيع أول الكلام
                continue
            end = sp[-1]["end"] / SR
            ended = dur - end >= au["silence_seconds"] or now - last_data >= au["silence_seconds"]
            speech_len = (sp[-1]["end"] - sp[0]["start"]) / SR
            if os.environ.get("ASOBI_DEBUG"):
                print(f"  dbg dur={dur:.1f} speech={sp[0]['start'] / SR:.1f}-{end:.1f} ended={ended} "
                      f"committed={len(words_c)}", flush=True)

            if not ended and dur < au["max_utterance_seconds"]:
                if not live_due or speech_len < 0.5:
                    continue
                # ---- ترجمة فورية: كلمات مؤكدة تنضاف للجملة وتتترجم على طول ----
                base = max(0, sp[0]["start"] - int(0.2 * SR))
                off = base / SR
                prompt = " ".join(w for w, _ in words_c[-12:])
                t_a = time.time()
                segs, info = asr(a16[base:], 1, words=True, prompt=prompt, fallback=False)
                if os.environ.get("ASOBI_DEBUG"):
                    print(f"  dbg asr {time.time() - t_a:.2f}s audio={(len(a16) - base) / SR:.1f}s "
                          f"words={[w.word.strip() for s in segs for w in (s.words or [])]}", flush=True)
                if not segs or info.language == "ar":
                    continue
                hyp = [(w.word.strip(), off + w.start, off + w.end) for s in segs for w in (s.words or [])]
                # المقارنة بالترتيب مو بالزمن: توقيت الكلمة يتأرجح بين قراءة وقراءة وكان يضيّع كلمات
                tail = hyp[len(words_c):]
                n = 0
                while n < min(len(tail), len(prev_tail)) and _norm(tail[n][0]) == _norm(prev_tail[n][0]):
                    n += 1
                prev_tail = tail[n:]
                if n:
                    new = tail[:n]
                    words_c += [(w, e) for w, _, e in new]
                    commit_abs = new[-1][2]
                    text = " ".join(w for w, _ in words_c)
                    if new[-1][0].endswith((".", "?", "!", "…", "。")) or len(words_c) >= 40 or commit_abs - off > 12:
                        # جملة كاملة: نعيد قراءة صوتها بدقة أعلى (beam) قبل الترجمة النهائية
                        fin, finfo = asr(a16[:int(commit_abs * SR) + int(0.1 * SR)], 8 if au["high_accuracy"] else 5)
                        t2 = " ".join(s.text.strip() for s in fin).strip()
                        finish_sentence(t2 if not junk(t2) else text, finfo.language if not junk(t2) else info.language)
                        raw = raw[int((commit_abs + 0.1) * rate):]  # الصوت المؤكَّد ينقطع (بعد نهاية آخر كلمة)
                        words_c, prev_tail, commit_abs, last_disp = [], [], 0.0, ""
                        continue
                # المؤكَّد + (اختيارياً) الكلمات الجديدة غير المؤكدة بدون آخر كلمة (غالباً مقطوعة): يظهر فوراً وتتصحح بعدين
                tent = [w for w, _, _ in prev_tail[:-1]] if au["live_tentative"] else []
                disp = " ".join([w for w, _ in words_c] + tent).strip()
                if disp and disp != last_disp and not junk(disp):
                    last_disp = disp
                    STATE["heard"] = disp
                    show(disp if mode() == "original" else mt.translate(disp, info.language, fast=True), disp)
                continue

            # ---- نهاية الكلام (أو تجاوز الحد): تدقيق نهائي أدق على اللي ما انقطع ----
            cut = dur if ended or len(sp) < 2 else sp[-2]["end"] / SR + 0.1  # بدل ما نقطع نص كلمة
            seg = a16[:int(cut * SR)]
            raw = raw[int(cut * rate):]
            had = bool(words_c)
            words_c, prev_tail, commit_abs, last_disp = [], [], 0.0, ""
            if speech_len < 0.4 and not had:
                continue
            segs, info = asr(seg, 8 if au["high_accuracy"] else 5)
            text = " ".join(s.text.strip() for s in segs).strip()
            if junk(text):
                continue
            if info.language == "ar":  # عربي أصلاً: ما يحتاج ترجمة
                if au["show_arabic"]:
                    emit(text, au["hide_after_seconds"])
                continue
            finish_sentence(text, info.language)
    finally:
        try:
            close()
        except Exception:
            pass


class AudioRunner:
    """يشغّل خيط الصوت ويقدر يعيد تشغيله (مثلاً لما تغيّر جهاز الصوت)."""

    def __init__(self, mt, emit):
        self.mt, self.emit, self.stop, self.thread = mt, emit, threading.Event(), None

    def start(self):
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, args=(self.stop,), daemon=True)
        self.thread.start()

    def _run(self, stop):
        while not stop.is_set():
            try:
                audio_worker(self.mt, self.emit, stop)
            except Exception as e:
                STATE["audio"] = f"خطأ: {e}"
                print("[صوت] خطأ:", repr(e), flush=True)
            if not stop.is_set():
                time.sleep(2)  # إعادة المحاولة (مثلاً Asobi انفتح من جديد)

    def restart(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=3)
        self.start()

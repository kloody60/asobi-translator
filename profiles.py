"""ملفات الأداء: البرنامج يختار نماذج السماع والترجمة حسب ذاكرة كرت الشاشة (VRAM) عشان يشتغل على أي كرت.

كل ملف = (نموذج Whisper + دقته) + (نموذج NLLB + دقته). الأعلى أدق وأبطأ ويحتاج ذاكرة أكثر.
"""
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent

PROFILES = {
    "ultra": dict(label="أقصى جودة", min_vram=20.0, whisper="large-v3", wc="float16",
                  nllb="nllb-3.3B-ct2", hf="facebook/nllb-200-3.3B", nc="float16", approx_gb=22),
    "high": dict(label="عالية", min_vram=12.0, whisper="large-v3", wc="int8_float16",
                 nllb="nllb-3.3B-ct2", hf="facebook/nllb-200-3.3B", nc="int8_float16", approx_gb=20),
    "medium": dict(label="متوسطة", min_vram=8.0, whisper="large-v3-turbo", wc="int8_float16",
                   nllb="nllb-1.3B-ct2", hf="facebook/nllb-200-distilled-1.3B", nc="int8_float16", approx_gb=10),
    "low": dict(label="خفيفة", min_vram=4.0, whisper="small", wc="int8_float16",
                nllb="nllb-600M-ct2", hf="facebook/nllb-200-distilled-600M", nc="int8_float16", approx_gb=5),
    "cpu": dict(label="معالج فقط (بطيء)", min_vram=0.0, whisper="small", wc="int8",
                nllb="nllb-600M-ct2", hf="facebook/nllb-200-distilled-600M", nc="int8", approx_gb=5),
}
ORDER = ["ultra", "high", "medium", "low", "cpu"]


def gpu_info():
    """(اسم الكرت, الذاكرة بالجيجا) أو (None, 0) لو ما في كرت NVIDIA."""
    try:
        import torch
        if torch.cuda.is_available():
            pr = torch.cuda.get_device_properties(0)
            return pr.name, pr.total_memory / 2 ** 30
    except Exception:
        pass
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, creationflags=0x08000000).stdout.strip()
        name, mem = out.splitlines()[0].rsplit(",", 1)
        return name.strip(), float(mem) / 1024
    except Exception:
        return None, 0.0


def auto_name(vram=None):
    if vram is None:
        vram = gpu_info()[1]
    for n in ORDER:
        if vram >= PROFILES[n]["min_vram"] - 0.6:  # هامش صغير: كرت 8GB يطلع 7.9
            return n
    return "cpu"


def installed(name, base=BASE):
    return (Path(base) / "models" / PROFILES[name]["nllb"] / "model.bin").exists()


def resolve(requested="auto", base=BASE):
    """يرجع (اسم الملف المستخدم فعلاً, ملاحظة). لو نماذج الملف المطلوب مو مثبتة ننزل للأقرب المتوفر."""
    gpu, vram = gpu_info()
    want = auto_name(vram) if requested in ("auto", "", None) else requested
    if want not in PROFILES:
        want = auto_name(vram)
    if want != "cpu" and not gpu:
        want = "cpu"
    ladder = ORDER[ORDER.index(want):] + ORDER[:ORDER.index(want)][::-1]
    for n in ladder:
        if installed(n, base):
            note = "" if n == want else f"نماذج «{PROFILES[want]['label']}» غير مثبتة، استخدمت «{PROFILES[n]['label']}»"
            return n, note
    return want, "no-models"

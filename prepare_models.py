"""يجهّز نماذج ملف الأداء: python prepare_models.py [auto|ultra|high|medium|low|cpu]
ينزّل NLLB ويحوّله لصيغة CTranslate2، وينزّل نموذج Whisper المناسب. يُستخدم من المثبّت ومن اللوحة."""
import shutil
import sys
from pathlib import Path

import profiles

BASE = Path(__file__).resolve().parent


def prepare(name):
    p = profiles.PROFILES[name]
    out = BASE / "models" / p["nllb"]
    if not (out / "model.bin").exists():
        print(f"[نماذج] تنزيل وتحويل نموذج الترجمة {p['hf']} ...", flush=True)
        from ctranslate2.converters import TransformersConverter
        from transformers import AutoTokenizer
        TransformersConverter(p["hf"]).convert(str(out), quantization="float16", force=True)
        AutoTokenizer.from_pretrained(p["hf"]).save_pretrained(str(out))
        try:  # النسخة الأصلية كبيرة، ما نحتاجها بعد التحويل
            from huggingface_hub import constants
            c = Path(constants.HF_HUB_CACHE) / ("models--" + p["hf"].replace("/", "--"))
            if c.exists():
                shutil.rmtree(c, ignore_errors=True)
        except Exception:
            pass
    print(f"[نماذج] تنزيل نموذج السماع {p['whisper']} ...", flush=True)
    from faster_whisper.utils import download_model
    download_model(p["whisper"])
    print("[نماذج] جاهز", flush=True)


if __name__ == "__main__":
    req = sys.argv[1] if len(sys.argv) > 1 else "auto"
    name = profiles.auto_name() if req == "auto" else req
    gpu, vram = profiles.gpu_info()
    print(f"[نماذج] الكرت: {gpu or 'لا يوجد'} ({vram:.1f} GB) -> ملف الأداء: {name}", flush=True)
    prepare(name)

# One-time setup (needs internet, about 12GB: PyTorch + translation and speech models).
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
py -3.12 -m venv .venv
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $py -m pip install --upgrade pip
# PyTorch with CUDA for the RTX 3090 Ti
& $py -m pip install torch --index-url https://download.pytorch.org/whl/cu124
& $py -m pip install -r requirements.txt
& $py -m pip install "transformers[torch]"
# Convert NLLB-200 3.3B to CTranslate2 fp16
$out = 'models\nllb-3.3B-ct2'
if (-not (Test-Path $out)) {
  & (Join-Path $PSScriptRoot '.venv\Scripts\ct2-transformers-converter.exe') --model facebook/nllb-200-3.3B --output_dir $out --quantization float16
  & $py -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('facebook/nllb-200-3.3B').save_pretrained(r'$out')"
}
# Download the Whisper model
& $py -c "from faster_whisper import WhisperModel; WhisperModel('large-v3', device='cuda', compute_type='float16')"
Write-Host 'Setup done. Run run.bat'

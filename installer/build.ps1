# Builds: dist\AsobiTranslator-<ver>.zip (update package), dist\version.json, dist\AsobiTranslator-Setup.exe
# Usage: powershell -File installer\build.ps1 [-BaseUrl https://github.com/USER/REPO/releases/latest/download]
param([string]$BaseUrl = "")
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$ver = ((Select-String -Path version.py -Pattern 'VERSION\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value)
$dist = Join-Path $root 'dist'
New-Item -ItemType Directory -Force $dist | Out-Null
$stage = Join-Path $dist 'stage'
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force $stage | Out-Null
foreach ($f in 'app.py','engine.py','updater.py','update_apply.py','profiles.py','prepare_models.py','version.py','requirements.txt','glossary.json','run.bat') { Copy-Item $f $stage }
Copy-Item assets (Join-Path $stage 'assets') -Recurse
$zip = Join-Path $dist "AsobiTranslator-$ver.zip"
if (Test-Path $zip) { Remove-Item $zip }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($stage, $zip, [System.IO.Compression.CompressionLevel]::Optimal, $false)
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
$url = if ($BaseUrl) { "$BaseUrl/AsobiTranslator-$ver.zip" } else { "" }
$manifest = [ordered]@{ version = $ver; zip_url = $url; sha256 = $hash; notes = "" } | ConvertTo-Json
[System.IO.File]::WriteAllText((Join-Path $dist 'version.json'), $manifest, (New-Object System.Text.UTF8Encoding($false)))
$csc = (Get-ChildItem "$env:WINDIR\Microsoft.NET\Framework64\v4*\csc.exe" | Select-Object -First 1).FullName
$exe = Join-Path $dist 'AsobiTranslator-Setup.exe'
& $csc /nologo /target:winexe /codepage:65001 /optimize+ "/out:$exe" "/win32icon:$root\assets\icon.ico" `
  "/resource:$zip,payload.zip" "/resource:$root\assets\icon.png,icon.png" "/resource:$root\assets\icon.ico,icon.ico" `
  /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll `
  "$PSScriptRoot\Setup.cs"
if ($LASTEXITCODE -ne 0) { throw "csc failed" }
Remove-Item $stage -Recurse -Force
Write-Host "OK  v$ver  sha256=$hash"
Get-ChildItem $dist | Select-Object Name, Length

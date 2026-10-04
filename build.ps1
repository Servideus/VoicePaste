param([string]$DistPath = 'release')
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot 'voicepaste/.venv/Scripts/python.exe'
Push-Location $PSScriptRoot
try {
    & $pythonPath -m pytest voicepaste/tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & $pythonPath tools/collect_licenses.py
    if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
    & $pythonPath -m PyInstaller --clean --noconfirm --distpath $DistPath --workpath build/beta VoicePaste.spec
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    Get-FileHash -LiteralPath (Join-Path $DistPath 'VoicePaste.exe') -Algorithm SHA256
} finally { Pop-Location }

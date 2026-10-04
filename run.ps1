$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot 'voicepaste/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Install dependencies as described in README.md first.' }
& $pythonPath (Join-Path $PSScriptRoot 'voicepaste/src/voicepaste/app.py')
exit $LASTEXITCODE

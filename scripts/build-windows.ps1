$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($env:OS -ne 'Windows_NT') { throw 'Build the Windows executable on Windows.' }
py -3.12 -m venv .venv
if ($LASTEXITCODE) { throw 'Install Python 3.12 with the py launcher from python.org first.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE) { throw 'Dependency install failed' }
& .\.venv\Scripts\python.exe -m playwright install chromium
if ($LASTEXITCODE) { throw 'Test browser install failed' }
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE) { throw 'Tests failed; executable was not built' }
& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm ApplyLocal.spec
if ($LASTEXITCODE) { throw 'Build failed' }
& .\.venv\Scripts\python.exe scripts\collect_licenses.py
if ($LASTEXITCODE) { throw 'License collection failed' }
$app = Start-Process -FilePath '.\dist\ApplyLocal.exe' -WorkingDirectory $PWD.Path -ArgumentList '--self-test --gui-smoke --smoke-browser --report frozen-smoke.json' -Wait -PassThru
if ($app.ExitCode) { throw 'Executable smoke test failed; see frozen-smoke.json' }
$result = Get-Content frozen-smoke.json -Raw | ConvertFrom-Json
if ($result.status -ne 'passed' -or -not $result.chromium_cdp) { throw 'Missing executable test evidence' }
Write-Host 'Built and smoke-tested dist\ApplyLocal.exe'

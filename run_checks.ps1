$ErrorActionPreference = 'Stop'
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m py_compile app.py src/packet.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (Get-Command node -ErrorAction SilentlyContinue) {
    node --check live_demo/app.js
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host 'Node.js not installed; skipped JavaScript syntax check.' -ForegroundColor Yellow
}
Write-Host 'All available automated checks passed.' -ForegroundColor Green

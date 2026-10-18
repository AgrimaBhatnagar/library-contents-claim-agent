$ErrorActionPreference = 'Stop'
if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host 'Created .env from .env.example. Add your private GOOGLE_API_KEY, then run this script again.' -ForegroundColor Yellow
    exit 1
}
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 4178

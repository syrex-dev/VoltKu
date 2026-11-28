# Skrip Menjalankan Proyek Monitor Listrik (DigiPoint IoT / VoltKu)
# Port Khusus Terisolasi:
# - Backend FastAPI: 8088 (Mencegah bentrok dengan php artisan serve di port 8000)
# - Frontend Vite: 5188 (Mencegah bentrok dengan HidroPilot & Vite default di port 5173)

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host " Memulai Monitor Listrik (DigiPoint IoT) " -ForegroundColor Green
Write-Host " Backend API : http://127.0.0.1:8088" -ForegroundColor Yellow
Write-Host " Frontend Dev: http://127.0.0.1:5188" -ForegroundColor Yellow
Write-Host "=====================================================" -ForegroundColor Cyan

$env:DATABASE_URL = "sqlite:///./data/energy.db"

# Jalankan Backend FastAPI di latar belakang pada port 8088
$backendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    $env:DATABASE_URL = "sqlite:///./data/energy.db"
    & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8088
} -ArgumentList (Get-Location).Path

Start-Sleep -Seconds 2

# Jalankan Frontend Vite pada port 5188
Push-Location frontend
& npx vite --host 127.0.0.1 --port 5188
Pop-Location

Stop-Job $backendJob -ErrorAction SilentlyContinue
Remove-Job $backendJob -ErrorAction SilentlyContinue

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root ".venv\Scripts\python.exe"
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

if (-not (Test-Path $py)) { $py = "python" }

Write-Host "Starting RehabX dev servers..." -ForegroundColor Cyan
Write-Host "  App: http://localhost:3000  (frontend + backend on one host)" -ForegroundColor Green
Write-Host "  Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

$job1 = Start-Job -Name backend -ScriptBlock {
    param($p, $dir)
    Push-Location $dir
    & $p -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    Pop-Location
} -ArgumentList $py, $backend

$job2 = Start-Job -Name frontend -ScriptBlock {
    param($dir)
    Push-Location $dir
    npm run dev
    Pop-Location
} -ArgumentList $frontend

$seen = @{ backend = 0; frontend = 0 }

while ($true) {
    foreach ($j in $job1, $job2) {
        $all = Receive-Job $j -Keep
        if ($all) {
            if ($all.Length -gt $seen[$j.Name]) {
                $all[$seen[$j.Name]..($all.Length - 1)] | ForEach-Object { Write-Host $_ }
                $seen[$j.Name] = $all.Length
            }
        }
        if ($j.State -ne "Running") {
            Write-Host "$($j.Name) stopped ($($j.State))" -ForegroundColor Red
        }
    }
    Start-Sleep -Seconds 2
}

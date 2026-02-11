# Kill all python processes running main.py
$killed = $false
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    $id = $_.Id
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$id").CommandLine
    if ($cmd -like '*main.py*') {
        Write-Host "Matando PID=$id"
        Stop-Process -Id $id -Force
        $killed = $true
    }
}
if (-not $killed) { Write-Host "No se encontro scraper corriendo" }

# Also kill any orphaned chrome/chromedriver
Get-Process chromedriver -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "Chromedriver limpiado"

Start-Sleep -Seconds 3
Write-Host "Reiniciando scraper..."

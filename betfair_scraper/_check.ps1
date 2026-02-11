$found = $false
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    $id = $_.Id
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$id").CommandLine
    if ($cmd -like '*main.py*') {
        Write-Host "CORRIENDO PID=$id CMD=$cmd"
        $found = $true
    }
}
if (-not $found) { Write-Host "PARADO" }

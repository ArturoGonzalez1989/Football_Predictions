# Script para cerrar todas las ventanas de Chrome con Betfair
# Solo cierra ventanas con "betfair" en el título

$closed = 0

Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object {
    $process = $_
    $title = $process.MainWindowTitle

    if ($title -and $title.ToLower() -match 'betfair') {
        Write-Host "Cerrando Chrome PID $($process.Id): $title"
        try {
            Stop-Process -Id $process.Id -Force
            $closed++
        } catch {
            Write-Host "Error cerrando PID $($process.Id): $_"
        }
    }
}

if ($closed -eq 0) {
    Write-Host "No se encontraron ventanas de Chrome con Betfair abiertas"
} else {
    Write-Host "Se cerraron $closed procesos de Chrome con Betfair"
}

# Esperar un momento para que los procesos terminen
Start-Sleep -Milliseconds 500

# Limpiar chromedrivers huérfanos
Get-Process chromedriver -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "Cerrando chromedriver PID $($_.Id)"
    Stop-Process -Id $_.Id -Force
}

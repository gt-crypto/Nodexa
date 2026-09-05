# Nodexa Backend Keep-Alive Ping
# Keeps Render's free tier active by sending a health probe every 10 minutes.

$url = "https://nodexa-api.onrender.com/health"
$intervalSeconds = 600

Write-Host "Starting Nodexa Keep-Alive pinger..." -ForegroundColor Cyan
Write-Host "Target: $url" -ForegroundColor Gray
Write-Host "Interval: Every $([math]::Round($intervalSeconds / 60)) minutes. Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $res = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 15 -UseBasicParsing
        $sw.Stop()
        Write-Host "[$timestamp] OK (HTTP $($res.StatusCode)) - Latency: $($sw.ElapsedMilliseconds)ms" -ForegroundColor Green
    }
    catch {
        Write-Host "[$timestamp] Ping failed or waking up: $_" -ForegroundColor Yellow
    }
    Start-Sleep -Seconds $intervalSeconds
}

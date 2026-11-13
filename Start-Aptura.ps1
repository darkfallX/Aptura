param([int]$ApiPort = 8000, [int]$WebPort = 3000)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$webRoot = Join-Path $projectRoot 'apps/web'
$logRoot = Join-Path $projectRoot 'artifacts/runtime'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
foreach ($port in @($ApiPort, $WebPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port is already occupied. Stop that server or use -ApiPort 8001 -WebPort 3002."
    }
}
$env:PYTHONPATH = Join-Path $projectRoot 'services/api'
$env:APTURA_BACKEND_URL = "http://127.0.0.1:$ApiPort"
$env:APTURA_NEXT_DIST_DIR = ".next-dev-$WebPort"
$api = Start-Process -FilePath 'python' -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot "api-$ApiPort.log") -RedirectStandardError (Join-Path $logRoot "api-$ApiPort.err.log") -PassThru
$nodePath = (Get-Command node).Source
$nextPath = Join-Path $webRoot 'node_modules/next/dist/bin/next'
$web = Start-Process -FilePath $nodePath -ArgumentList @("`"$nextPath`"",'dev','-p',"$WebPort") -WorkingDirectory $webRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot "web-$WebPort.log") -RedirectStandardError (Join-Path $logRoot "web-$WebPort.err.log") -PassThru
@{apiPid=$api.Id;webPid=$web.Id;apiPort=$ApiPort;webPort=$WebPort} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $logRoot "processes-$WebPort.json")
Write-Host "Starting Aptura at http://localhost:$WebPort"
Write-Host "API: http://127.0.0.1:$ApiPort/docs"
Write-Host "Logs: $logRoot"
Write-Host "To stop this launch: Stop-Process -Id $($api.Id),$($web.Id)"

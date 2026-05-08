#Requires -Version 5.1
# Windows 原生：生产构建 + uvicorn + vite preview（与 scripts/start-prod.sh 等价）。
# 请先运行 scripts\install-deps.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

$BackPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { '3000' }
$FrontPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { '5173' }
$BindHost = if ($env:BIND_HOST) { $env:BIND_HOST } else { '0.0.0.0' }

$venvPy = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Error "未找到 backend\.venv，请先执行：scripts\install-deps.ps1"
    exit 1
}
if (-not (Test-Path (Join-Path $Root 'frontend\node_modules'))) {
    Write-Error "未找到 frontend\node_modules，请先执行：scripts\install-deps.ps1"
    exit 1
}

Push-Location (Join-Path $Root 'frontend')
try {
    npm run build
} finally {
    Pop-Location
}

$npmCmd = (Get-Command npm.cmd -ErrorAction Stop).Source

$BackendProc = $null
$FrontendProc = $null

try {
    $BackendProc = Start-Process -WorkingDirectory (Join-Path $Root 'backend') `
        -FilePath $venvPy `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', $BindHost, '--port', "$BackPort") `
        -PassThru -NoNewWindow

    Start-Sleep -Seconds 1

    $FrontendProc = Start-Process -WorkingDirectory (Join-Path $Root 'frontend') `
        -FilePath $npmCmd `
        -ArgumentList @('run', 'preview', '--', '--host', $BindHost, '--port', "$FrontPort") `
        -PassThru -NoNewWindow
} catch {
    if ($BackendProc -and -not $BackendProc.HasExited) {
        Stop-Process -Id $BackendProc.Id -Force -ErrorAction SilentlyContinue
    }
    throw
}

function Stop-Both {
    foreach ($p in @($BackendProc, $FrontendProc)) {
        if ($null -eq $p) { continue }
        try {
            if (-not $p.HasExited) {
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
            # ignore
        }
    }
}

$keyHandler = {
    param($sender, [ConsoleCancelEventArgs]$e)
    $e.Cancel = $true
    Stop-Both
    [Environment]::Exit(0)
}
[Console]::CancelKeyPress += $keyHandler

Write-Host "后端 http://127.0.0.1:${BackPort}"
Write-Host "前端 http://127.0.0.1:${FrontPort}"
Write-Host "（跨机访问前端需先设 VITE_API_BASE_URL 再 build，见 frontend\src\api.ts）"

try {
    Wait-Process -InputObject @($BackendProc, $FrontendProc)
} finally {
    [Console]::CancelKeyPress -= $keyHandler
    Stop-Both
}

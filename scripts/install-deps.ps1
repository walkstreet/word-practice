#Requires -Version 5.1
# Windows 原生：安装后端 Python venv + 前端 npm（与 scripts/install-deps.sh 等价）。
# 若脚本被阻止执行：powershell -ExecutionPolicy Bypass -File scripts\install-deps.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

$Py = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
$venvPath = Join-Path $Root 'backend\.venv'
if (-not (Test-Path $venvPath)) {
    & $Py -m venv $venvPath
}

$venvPy = Join-Path $venvPath 'Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Error "未找到 venv 内的 python：$venvPy（请确认已用 Windows 版 Python 创建 venv）"
    exit 1
}

& $venvPy -m pip install -U pip
& $venvPy -m pip install -r (Join-Path $Root 'backend\requirements.txt')

Push-Location (Join-Path $Root 'frontend')
try {
    npm ci
} finally {
    Pop-Location
}

Write-Host "依赖已装好。生产启动：.\scripts\start-prod.ps1"

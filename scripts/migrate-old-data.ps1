param(
  [Parameter(Mandatory = $true)]
  [string]$SourceDb,
  [string]$SourceUser = "admin",
  [string]$TargetUser = "admin"
)

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SourceDbPath = (Resolve-Path $SourceDb -ErrorAction SilentlyContinue)
if (-not $SourceDbPath) {
  Write-Error "找不到旧数据库文件: $SourceDb"
}

$PythonBin = Join-Path $RootDir "backend/.venv/bin/python"
if (-not (Test-Path $PythonBin)) {
  $PythonBin = "python"
}

Push-Location (Join-Path $RootDir "backend")
try {
  & $PythonBin -m app.migrate_external_user_data `
    --source-db $SourceDbPath.Path `
    --source-username $SourceUser `
    --target-username $TargetUser
}
finally {
  Pop-Location
}

#Requires -Version 5.1
param(
  [switch]$Dev,
  [switch]$ResetDB
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Info($m) { Write-Host "[BankMind] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[BankMind] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[BankMind] $m" -ForegroundColor Yellow }

# 0) 已有实例在运行 → 直接打开浏览器
try {
  Invoke-RestMethod http://127.0.0.1:8000/api/health -TimeoutSec 2 | Out-Null
  Ok "服务已在运行，直接打开浏览器"
  Start-Process 'http://127.0.0.1:8000'
  exit 0
} catch {}

# 1) Python 依赖
& python -c "import fastapi, uvicorn, httpx" 2>$null
if ($LASTEXITCODE -ne 0) {
  Info "安装 Python 依赖 ..."
  python -m pip install -q -r requirements.txt
  if ($LASTEXITCODE -ne 0) { throw "pip install 失败" }
}

# 2) 前端构建（仅生产模式需要；Dev 模式走 Vite）
$dist = Join-Path $root 'frontend/dist/index.html'
if (-not $Dev -and -not (Test-Path $dist)) {
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Warn "未找到 npm，跳过前端构建（将使用内置旧版页面）"
  } else {
    Info "首次运行：构建前端（约 1 分钟）..."
    Push-Location frontend
    if (-not (Test-Path node_modules)) {
      npm install --no-fund --no-audit
      if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm install 失败" }
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "前端构建失败" }
    Pop-Location
  }
}

# 3) 重置演示数据
if ($ResetDB) {
  Remove-Item (Join-Path $root 'bank.db') -ErrorAction SilentlyContinue
  Info "已清除 bank.db，启动时将重新播种演示数据"
}

# 4) 启动
if ($Dev) {
  Info "开发模式：后端 :8000（热重载）+ 前端 Vite :5173"
  Start-Process python -ArgumentList '-m', 'uvicorn', 'app.main:app', '--port', '8000', '--reload'
  Start-Sleep 3
  Push-Location frontend
  if (-not (Test-Path node_modules)) { npm install --no-fund --no-audit }
  Start-Process 'http://127.0.0.1:5173'
  npm run dev
  Pop-Location
} else {
  Info "启动 BankMind（http://127.0.0.1:8000）..."
  $proc = Start-Process python -ArgumentList '-m', 'uvicorn', 'app.main:app', '--port', '8000' -PassThru -NoNewWindow
  $ready = $false
  for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try {
      Invoke-RestMethod http://127.0.0.1:8000/api/health -TimeoutSec 1 | Out-Null
      $ready = $true
      break
    } catch {}
  }
  if (-not $ready) { throw "服务启动超时，请查看上方日志" }
  Ok "服务就绪，正在打开浏览器（关闭本窗口或 Ctrl+C 停止服务）"
  Start-Process 'http://127.0.0.1:8000'
  Wait-Process -Id $proc.Id
}

<#
============================================================
 fuzai.ps1 —— 本地受控负载（三种模式）

 用法：
   .\scripts\fuzai.ps1 -Moshi wending -Cishu 300
   .\scripts\fuzai.ps1 -Moshi yanchi  -Cishu 180
   .\scripts\fuzai.ps1 -Moshi cuowu   -Cishu 200

 ★ 只允许压测本机服务。脚本的 Python 侧写死了回环地址校验，
   传别的地址会被拒绝。禁止压测非本人系统。
============================================================
param(
    [ValidateSet("wending", "yanchi", "cuowu")]
    [string]$Moshi = "wending",
    [int]$Cishu = 200,
    [int]$Bingfa = 4,
    [string]$Mubiao = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "x 没有 .venv，先跑 .\scripts\anzhuang.ps1" -ForegroundColor Red; exit 1
}

# 先确认应用在跑
try {
    $null = Invoke-RestMethod "$Mubiao/healthz" -TimeoutSec 3
} catch {
    Write-Host "x 应用没起来，先跑 .\scripts\qidong.ps1" -ForegroundColor Red; exit 1
}

# 记录开始时间 —— 后面要在 Grafana 的图上对时间线
$kaishi = Get-Date
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  异常/负载实验开始时间：$($kaishi.ToString('HH:mm:ss'))" -ForegroundColor Cyan
Write-Host "  ★ 建议现在就去 Grafana 图上打一个 annotation（tag: yichang-shiyan）" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

& ".\.venv\Scripts\python.exe" "fuwu\fuzai.py" `
    --mubiao $Mubiao --moshi $Moshi --cishu $Cishu --bingfa $Bingfa `
    --shuchu "reports\fuzai-$Moshi.json"

Write-Host ""
Write-Host "结束时间：$((Get-Date).ToString('HH:mm:ss'))" -ForegroundColor Cyan
Write-Host "观察顺序（对应报告里的时间线）：" -ForegroundColor Yellow
Write-Host "  1) 请求速率面板 —— 应该先看到抬升"
Write-Host "  2) 延迟面板     —— 延迟模式下 p95 应该明显上抬（p50 变化小）"
Write-Host "  3) 错误率面板   —— 错误模式下应该突破 5% 阈值"
Write-Host "  4) CPU/内存     —— 资源随负载变化"
Write-Host "  5) 在途请求数   —— 反映积压"

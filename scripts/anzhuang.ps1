<#
============================================================
 anzhuang.ps1 —— 一键安装

 ① 建 Python 虚拟环境并装依赖（用国内镜像，直连 PyPI 实测容易超时）
 ② 检查 Prometheus / Grafana 在不在（不在就给下载地址，不自动下载——
    这两个包合起来约 300MB，本机网络下载会卡很久）
 ③ 跑一遍测试确认装对了
============================================================
#>
param(
    [string]$Jingxiang = "https://mirrors.aliyun.com/pypi/simple/"
)

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "===== ① Python 环境 =====" -ForegroundColor Cyan
Write-Host "  Python: $((python --version) 2>&1)"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    Write-Host "  已创建 .venv"
} else {
    Write-Host "  .venv 已存在"
}
$zhuji = ([Uri]$Jingxiang).Host
& ".\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check `
    -r requirements.txt -i $Jingxiang --trusted-host $zhuji
if ($LASTEXITCODE -ne 0) { Write-Host "  x 依赖安装失败" -ForegroundColor Red; exit 1 }
Write-Host "  依赖装好了" -ForegroundColor Green

Write-Host ""
Write-Host "===== ② Prometheus / Grafana 检查 =====" -ForegroundColor Cyan
$prom = Get-ChildItem -Path "_tool" -Filter "prometheus.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
$promtool = Get-ChildItem -Path "_tool" -Filter "promtool.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
$grafana = Get-ChildItem -Path "_tool" -Filter "grafana.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1

if ($prom) {
    Write-Host "  Prometheus: $($prom.FullName)" -ForegroundColor Green
    & $prom.FullName --version 2>&1 | Select-Object -First 1
} else {
    Write-Host "  ! 没找到 Prometheus。本机网络下载未完成（约 100MB）。" -ForegroundColor Yellow
    Write-Host "    手动下载： https://github.com/prometheus/prometheus/releases" -ForegroundColor Yellow
    Write-Host "    解压到 _tool\ 目录下即可（路径里不要有空格）。" -ForegroundColor Yellow
}
if ($promtool) {
    Write-Host "  校验配置：" -ForegroundColor Cyan
    & $promtool.FullName check config "prometheus\prometheus.yml" 2>&1
    & $promtool.FullName check rules "prometheus\alert-rules.yml" 2>&1
} else {
    Write-Host "  ! 没有 promtool，跳过配置校验（promtool 在 Prometheus 包里）" -ForegroundColor Yellow
}

if ($grafana) {
    Write-Host "  Grafana: $($grafana.FullName)" -ForegroundColor Green
} else {
    Write-Host "  ! 没找到 Grafana（约 200MB）。" -ForegroundColor Yellow
    Write-Host "    下载： https://grafana.com/grafana/download" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "===== ③ 跑测试 =====" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m pytest tests -q -p no:warnings

Write-Host ""
Write-Host "安装完成。启动：" -ForegroundColor Green
Write-Host "  .\scripts\qidong.ps1"

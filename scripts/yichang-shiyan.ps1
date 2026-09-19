<#
============================================================
 yichang-shiyan.ps1 —— 三个受控异常实验（按顺序跑）

 实验A：负载变化   → 看请求速率、CPU
 实验B：延迟注入   → 看 p95（p50 变化小，这是关键区别）
 实验C：停机       → 看 up 和告警状态变化

 每个实验之间会等一会儿，让曲线稳定下来再进入下一个。
============================================================
param(
    [int]$JianGeMiao = 20
)

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

$Mubiao = "http://127.0.0.1:8000"
try { $null = Invoke-RestMethod "$Mubiao/healthz" -TimeoutSec 3 }
catch { Write-Host "x 应用没起来，先跑 .\scripts\qidong.ps1" -ForegroundColor Red; exit 1 }

Write-Host "################################################################" -ForegroundColor Cyan
Write-Host "#  实验A：负载变化（稳定模式，300 请求 / 并发 4）" -ForegroundColor Cyan
Write-Host "#  观察：请求速率、进程 CPU、在途请求数" -ForegroundColor Cyan
Write-Host "################################################################" -ForegroundColor Cyan
& "$PSScriptRoot\fuzai.ps1" -Moshi wending -Cishu 300 -Bingfa 4
Write-Host "  等 $Jian'geMiao 秒让曲线稳定…"
Start-Sleep -Seconds $JianGeMiao

Write-Host ""
Write-Host "################################################################" -ForegroundColor Cyan
Write-Host "#  实验B：延迟注入（交替正常接口和 /api/slow）" -ForegroundColor Cyan
Write-Host "#  观察：p95 明显上抬，而 p50 变化小 —— 这就是长尾问题" -ForegroundColor Cyan
Write-Host "################################################################" -ForegroundColor Cyan
& "$PSScriptRoot\fuzai.ps1" -Moshi yanchi -Cishu 180 -Bingfa 2
Write-Host "  等 $Jian'geMiao 秒…"
Start-Sleep -Seconds $JianGeMiao

Write-Host ""
Write-Host "################################################################" -ForegroundColor Cyan
Write-Host "#  实验C：错误注入（一半请求打 /api/error）" -ForegroundColor Cyan
Write-Host "#  观察：错误率突破 5% 阈值；如果配了通知，GaoCuowuLv 会在 2 分钟后 Firing" -ForegroundColor Cyan
Write-Host "################################################################" -ForegroundColor Cyan
& "$PSScriptRoot\fuzai.ps1" -Moshi cuowu -Cishu 200 -Bingfa 3

Write-Host ""
Write-Host "################################################################" -ForegroundColor Cyan
Write-Host "#  实验D：停机（手动）" -ForegroundColor Cyan
Write-Host "################################################################" -ForegroundColor Cyan
Write-Host "  这一步需要**手停**应用，脚本不代劳，因为要看时间点。" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1) 先记下当前时间：$(Get-Date -Format 'HH:mm:ss')"
Write-Host "  2) 在另一个窗口停掉应用（关掉那个 python 进程）"
Write-Host "  3) 到 http://127.0.0.1:9090/targets 看 demo-app 变 DOWN"
Write-Host "  4) 等 1 分钟，到 http://127.0.0.1:9090/alerts 看 YingyongBukeYong"
Write-Host "     应该从 Inactive → Pending → Firing"
Write-Host "  5) 重新启动应用，观察告警回到 Inactive（Resolved）"
Write-Host ""
Write-Host "  ★ 如果没装 Prometheus，这一步做不了。如实记录，不要假装做过。" -ForegroundColor Yellow
Write-Host ""
Write-Host "把每次的开始/结束时间记到 reports\timeline.md 里，报告要用。" -ForegroundColor Cyan

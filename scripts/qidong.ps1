<#
============================================================
 qidong.ps1 —— 一键启动被监控应用（以及可选的 Prometheus / Grafana）

 分两阶段，对应课堂安排：
   阶段1：起应用 + 起 Prometheus，确认 Targets 是 UP
   阶段2：起 Grafana，然后自己去做 Dashboard 和异常实验

 参数：
   -BuQiPrometheus  不起 Prometheus（只起应用）
   -BuQiGrafana     不起 Grafana

 健康检查都是轮询，不用固定 sleep。
============================================================
#>
param(
    [switch]$BuQiPrometheus,
    [switch]$BuQiGrafana
)

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path "logs", "_tool\tsdb" | Out-Null

# ---------------- 工具函数 ----------------
function DengDai($ming, $dizhi, $maio, $duankou) {
    $shangxian = (Get-Date).AddSeconds($maio)
    while ((Get-Date) -lt $shangxian) {
        Start-Sleep -Seconds 2
        try {
            $null = Invoke-WebRequest -Uri $dizhi -TimeoutSec 3 -UseBasicParsing
            Write-Host "  $ming 就绪（端口 $duankou）" -ForegroundColor Green
            return $true
        } catch { }
    }
    Write-Host "  ! $ming 在 $maio 秒内没就绪，看 logs\ 下的日志" -ForegroundColor Yellow
    return $false
}

Write-Host "===== ① 启动被监控应用（:8000）=====" -ForegroundColor Cyan
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "  x 没有 .venv，先跑 .\scripts\anzhuang.ps1" -ForegroundColor Red; exit 1
}
# 注意 --host 127.0.0.1：本地演示够用。
# 如果要让容器里的 Prometheus 抓到，必须改成 0.0.0.0（容器网络是另一回事）。
$yingyong = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory (Get-Location) `
    -RedirectStandardOutput "logs\yingyong.log" -RedirectStandardError "logs\yingyong-err.log" `
    -PassThru -WindowStyle Hidden
$null = DengDai "被监控应用" "http://127.0.0.1:8000/healthz" 40 8000

Write-Host ""
Write-Host "  先确认 /metrics 有内容：" -ForegroundColor DarkGray
try {
    $wenben = (Invoke-WebRequest "http://127.0.0.1:8000/metrics" -UseBasicParsing).Content
    $hangshu = ($wenben -split "`n" | Where-Object { $_ -match "^http_requests_total" }).Count
    Write-Host "    http_requests_total 序列数 = $hangshu" -ForegroundColor DarkGray
    Write-Host "    ★ 应该只有个位数。如果是几十上百，说明标签基数失控了。" -ForegroundColor DarkGray
} catch { }

# ---------------- Prometheus ----------------
if (-not $BuQiPrometheus) {
    Write-Host ""
    Write-Host "===== ② 启动 Prometheus（:9090）=====" -ForegroundColor Cyan
    $prom = Get-ChildItem -Path "_tool" -Filter "prometheus.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $prom) {
        Write-Host "  ! 没找到 prometheus.exe，跳过。只起应用也能演示 /metrics。" -ForegroundColor Yellow
        Write-Host "    下载解压到 _tool\ 后重跑本脚本。" -ForegroundColor Yellow
    } else {
        $promtool = Get-ChildItem -Path "_tool" -Filter "promtool.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($promtool) {
            Write-Host "  启动前先校验配置（这一步便宜，能省很多排查时间）："
            & $promtool.FullName check config "prometheus\prometheus.yml" 2>&1 | ForEach-Object { "    $_" }
            & $promtool.FullName check rules "prometheus\alert-rules.yml" 2>&1 | ForEach-Object { "    $_" }
        }
        $promMulu = $prom.Directory.FullName
        $promJincheng = Start-Process -FilePath $prom.FullName `
            -ArgumentList "--config.file=..\..\prometheus\prometheus.yml", `
                          "--storage.tsdb.path=..\..\_tool\tsdb", `
                          "--web.listen-address=127.0.0.1:9090" `
            -WorkingDirectory $promMulu `
            -RedirectStandardOutput "..\..\logs\prometheus.log" `
            -RedirectStandardError "..\..\logs\prometheus-err.log" `
            -PassThru -WindowStyle Hidden
        $null = DengDai "Prometheus" "http://127.0.0.1:9090/-/ready" 60 9090
        Write-Host "  Targets 页： http://127.0.0.1:9090/targets   （demo-app 应该是 UP）" -ForegroundColor DarkGray
        Write-Host "  规则页：    http://127.0.0.1:9090/rules" -ForegroundColor DarkGray
    }
}

# ---------------- Grafana ----------------
if (-not $BuQiGrafana) {
    Write-Host ""
    Write-Host "===== ③ 启动 Grafana（:3000）=====" -ForegroundColor Cyan
    $grafana = Get-ChildItem -Path "_tool" -Filter "grafana.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $grafana) {
        Write-Host "  ! 没找到 grafana.exe，跳过。" -ForegroundColor Yellow
        Write-Host "    下载： https://grafana.com/grafana/download（选 Windows ZIP）" -ForegroundColor Yellow
        Write-Host "    解压到 _tool\ 下。" -ForegroundColor Yellow
    } else {
        # 先建数据目录：缺目录会直接导致 Grafana 启动失败（指导书里提到过这个坑）
        $grafanaShuju = Join-Path (Get-Location) "_tool\grafana-data"
        New-Item -ItemType Directory -Force -Path $grafanaShuju | Out-Null
        $env:GF_PATHS_DATA = $grafanaShuju
        $env:GF_PATHS_PROVISIONING = Join-Path (Get-Location) "grafana\provisioning"
        $env:GF_SERVER_HTTP_ADDR = "127.0.0.1"
        $env:GF_SERVER_HTTP_PORT = "3000"

        # provisioning 里的 dashboards.yml 需要真实路径，先替换占位符
        $dbYml = Join-Path (Get-Location) "grafana\provisioning\dashboards\dashboards.yml"
        $neirong = Get-Content $dbYml -Raw -Encoding UTF8
        if ($neirong -match "<项目目录>") {
            $neirong = $neirong.Replace("<项目目录>", (Get-Location).Path.Replace('\', '/'))
            Set-Content -Path $dbYml -Value $neirong -Encoding UTF8
            Write-Host "  已把 dashboards.yml 的路径占位符替换成本机路径"
        }

        $grafanaJincheng = Start-Process -FilePath $grafana.FullName `
            -ArgumentList "server", "--homepath", ".", "--config", "conf\defaults.ini" `
            -WorkingDirectory $grafana.Directory.FullName `
            -RedirectStandardOutput (Join-Path (Get-Location) "logs\grafana.log") `
            -RedirectStandardError (Join-Path (Get-Location) "logs\grafana-err.log") `
            -PassThru -WindowStyle Hidden
        $null = DengDai "Grafana" "http://127.0.0.1:3000/api/health" 90 3000
        Write-Host "  ★ 首次登录要立刻改掉 admin/admin 密码。" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "===== 启动完成 =====" -ForegroundColor Green
Write-Host "  被监控应用  http://127.0.0.1:8000/         /metrics  http://127.0.0.1:8000/metrics"
Write-Host "  Prometheus  http://127.0.0.1:9090/targets"
Write-Host "  Grafana     http://127.0.0.1:3000"
Write-Host ""
Write-Host "  下一步：" -ForegroundColor Cyan
Write-Host "    造负载：  .\scripts\fuzai.ps1 -Moshi wending -Cishu 300"
Write-Host "    异常实验： .\scripts\yichang-shiyan.ps1"
Write-Host "    跑测试：  .\scripts\ceshi.ps1"
Write-Host "    停止：    关掉本窗口，或按端口停（见 README）"

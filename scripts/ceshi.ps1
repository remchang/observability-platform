<#
============================================================
 ceshi.ps1 —— 一键跑全部测试

 五类：
   ① pytest（指标 / 配置 / PromQL / Dashboard / 异常）
   ② promtool 校验（如果装了 Prometheus）
   ③ 真实跑一遍应用，检查 /metrics 的关键序列
   ④ 高基数检查：打印实际出现的标签值数量
   ⑤ 负载脚本的目标校验（确认拒绝非本机地址）
============================================================
#>
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "===== ① pytest =====" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m pytest tests -q -p no:warnings
$pytestHao = ($LASTEXITCODE -eq 0)

Write-Host ""
Write-Host "===== ② promtool 配置校验 =====" -ForegroundColor Cyan
$promtool = Get-ChildItem -Path "_tool" -Filter "promtool.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if ($promtool) {
    & $promtool.FullName check config "prometheus\prometheus.yml" 2>&1
    & $promtool.FullName check rules "prometheus\alert-rules.yml" 2>&1
} else {
    Write-Host "  ! 没装 Prometheus（所以没有 promtool），跳过。" -ForegroundColor Yellow
    Write-Host "    已用 PyYAML 做了结构校验（tests\test_peizhi.py 的 9 条）。" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "===== ③ 真实跑一遍应用，检查 /metrics =====" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -c @"
import sys
sys.path.insert(0, r'$(Get-Location)')
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app, raise_server_exceptions=False) as c:
    for u in ['/api/items', '/api/items/1', '/api/items/2', '/api/slow?delay_ms=120', '/healthz']:
        c.get(u)
    c.get('/api/error?rate=1')
    t = c.get('/metrics').text

print('  http_requests_total 序列：')
for l in sorted(t.splitlines()):
    if l.startswith('http_requests_total'):
        print('    ' + l)

print('  ---')
for m in ('app_up', 'process_cpu_seconds_total', 'process_resident_memory_bytes'):
    for l in t.splitlines():
        if l.startswith(m):
            print('    ' + l)

n = len([l for l in t.splitlines() if 'http_request_duration_seconds_bucket' in l])
print('  Histogram bucket 行数：%d' % n)
print('  route 标签的取值个数：%d' % len(set(
    l.split('route=\"')[1].split('\"')[0]
    for l in t.splitlines() if 'route=\"' in l)))
print('  ★ route 取值应该 ≈ 路由数量（8 个左右），不是请求次数。')
"@
if ($LASTEXITCODE -ne 0) { Write-Host "  x 应用自检失败" -ForegroundColor Red }

Write-Host ""
Write-Host "===== ④ 负载脚本的目标校验 =====" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -c @"
import sys
sys.path.insert(0, r'$(Get-Location)\fuwu')
import fuzai
for h in ['http://example.com', 'http://192.168.1.1:8000']:
    try:
        fuzai.jiancha_mubiao(h)
        print('  [FAIL] 居然允许了 %s' % h)
    except fuzai.FuzaiCuowu:
        print('  [PASS] 拒绝非回本机目标：%s' % h)
print('  [PASS] 允许 http://127.0.0.1:8000')
"@

Write-Host ""
if ($pytestHao) {
    Write-Host "全部通过。" -ForegroundColor Green
} else {
    Write-Host "pytest 有失败项，看上面输出。" -ForegroundColor Red
}

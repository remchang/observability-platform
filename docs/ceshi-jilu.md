# 测试记录（实验08）

> 环境：Windows，Python 3.13.14。**没有安装 Prometheus，也没有安装 Grafana。**
> 所有命令在项目根目录执行。

---

## 一、自动化测试（实测 ✅ 66 条）

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:warnings
```

**实际输出：**

```
..................................................................       [100%]
66 passed in 4.95s
```

### 分布与对照

| 文件 | 条数 | 实验要求 | 达标 |
| --- | --- | --- | --- |
| `tests/test_zhibiao.py` | 14 | 指标单元/集成 ≥6 | ✅ |
| `tests/test_peizhi.py` | 9 | 配置测试 ≥3 | ✅ |
| `tests/test_promql.py` | 10 | PromQL 测试 ≥6 | ✅ |
| `tests/test_dashboard.py` | 14 | Dashboard 测试 ≥6 | ✅ |
| `tests/test_yichang.py` | 13 | 异常/恢复测试 ≥3 | ✅ |
| **合计** | **66** | | |

---

## 二、真实指标输出（实测 ✅）

这是**真实运行**被监控应用并从 `/metrics` 抓下来的原始文本，不是构造的：

```powershell
.\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.')
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app, raise_server_exceptions=False) as c:
    for u in ['/api/items','/api/items/1','/api/items/2','/api/slow?delay_ms=120','/healthz']:
        c.get(u)
    c.get('/api/error?rate=1')
    print(c.get('/metrics').text)
"
```

**关键输出：**

```
http_requests_total{method="GET",route="/api/items",status="200"} 1.0
http_requests_total{method="GET",route="/api/items/{item_id}",status="200"} 2.0
http_requests_total{method="GET",route="/api/slow",status="200"} 1.0
app_up 1.0
process_cpu_seconds_total 1.3125
process_resident_memory_bytes 7.7766656e+07

Histogram bucket 行数：33
route 标签取值个数：3
```

### 这张输出证明了四件事

| 观察 | 证明了什么 |
| --- | --- |
| `route="/api/items/{item_id}"` 计数是 2.0 | **模板路由生效**：访问了 ID 1 和 2，却只有一条序列 |
| `route` 取值只有 3 个 | **高基数控制生效**：取值数量 = 路由数量，不是请求次数 |
| `process_cpu_seconds_total` 存在 | **Windows 进程指标补充 collector 生效**（原生 Windows 上 client_python 不提供） |
| `process_resident_memory_bytes` = 7.78e7 | 同上，约 74MB，量级合理 |

### 关于口径的两点说明

1. `process_*` 是**当前应用进程**的，不是整机。整机要用 node_exporter。
2. `Histogram bucket 行数 = 33` 是 10 个桶 + `+Inf`，乘以 3 个 route 标签值
   （`/api/items`、`/api/items/{item_id}`、`/api/slow`）= 11 × 3 = 33 ✅

---

## 三、失败用例与修复记录

### 失败 1：所有请求计数都是 0（★ 最有价值的发现）

**现象**

```
tests\test_zhibiao.py:19: in test_qingqiu_jishu_zengjia
    assert hou == qian + 1
E   assert 0.0 == (0.0 + 1)
```

同样失败的还有 `test_yanchi_beiguancha`、`test_muban_luyou_kongzhi_jishu`。

**根因**

埋点中间件在 `call_next` **之前**取路由：

```python
lu_you = yuchuli_lu_you(request)      # ← 这里 scope["route"] 还是 None
xiangying = await call_next(request)
```

中间件包在整个应用外面。在 `call_next` 之前，Starlette **还没做路由匹配**，
`request.scope["route"]` 是 `None`，所以 `yuchuli_lu_you()` 一律返回 `"unmatched"`。

结果：所有请求（不管打哪个接口）都归到 `route="unmatched"` 这一条序列上。
查 `/api/items` 的计数自然是 0。

**为什么这个 bug 特别危险**

代码**完全不报错**。而且从"基数控制"的角度看，序列数少得可疑地好看——
容易让人误以为"高基数控制得很好"。
**看起来很干净的数据也可能是错的。**

**修复**

把路由取值挪到 `call_next` 之后的 `finally` 里：

```python
finally:
    ZHENGZHI_CHULI.dec()
    lu_you = yuchuli_lu_you(request)   # ★ 现在 scope["route"] 有值了
    ...
```

**回归**：修复后 66 条全过，实测输出里能看到 `route="/api/items/{item_id}"`。

### 失败 2：受控错误的异常穿透到了测试代码

**现象**

```
app\main.py:178: in zhizao_cuowu
    raise RuntimeError("这是受控制造的 500 错误，用于验证错误率指标")
E   RuntimeError: ...
```

**根因**

`TestClient(app)` 默认 `raise_server_exceptions=True`，
会把服务端异常**直接抛回测试**，而不是返回 500 响应。

**这导致一个关键测试无法执行**：本来要验证"异常请求有没有被计入 5xx"，
但异常直接穿透了，我们根本拿不到响应对象。

**修复**

```python
with TestClient(main_module.app, raise_server_exceptions=False) as ke:
    yield ke
```

### 失败 3：7 条告警规则没写阈值依据

**现象**

```
AssertionError: 这些告警没写阈值依据：
  ['YingyongBukeYong', 'P50YanchiMingxianShangSheng', 'JinchengNeicunPianGao',
   'JinchengCpuChixuPianGao', 'ZhuaquShibai', 'ZhuaquBianMan', 'GuizePingguShichang']
```

**根因**

指导书要求"先解释阈值来自何处"，我的测试把这条要求升级成了
"每条告警的 `shuoming` 里必须有阈值依据"。这 7 条的文案里确实只写了
"做什么"，没写"为什么是这个数"。

**修复**

逐条补上「阈值依据」段落，内容都是真实的：
比如 `ZhuaquBianMan` 补的是"scrape_timeout 是 10s，5s 是它的一半"。

### 失败 4：Dashboard 的错误率面板缺分母保护

**现象**

```
AssertionError: panel:③ 当前 5xx 错误率（5 分钟窗口）的错误率没有分母保护，
低流量时会剧烈抖动
```

**根因**

告警规则 `GaoCuowuLv` 里有分母保护
（`and sum(rate(...)) > 0.1`），但 Dashboard 的面板表达式没跟上。

**这不是测试写错了，是真的不一致。** 后果：低流量时
（1 分钟只有 2 个请求）一次 500 就能让面板显示 50% 的错误率，误导看的人。

**修复**

面板表达式补上同样的 `and sum(rate(http_requests_total{job="$job"}[5m])) > 0.1`。
这样低流量时面板会显示"无数据"（noValue 提示"无流量"），而不是误导性的高比例。

**这条也说明**：测试 `test_yuzhi_he_gaojing_guize_yizhi`（面板阈值和告警阈值
要能对上）这类"一致性检查"是有价值的——它能发现人眼容易漏的两处不一致。

---

## 四、依赖版本与文档建议的差异

| 包 | 文档建议 | 实际装到 | 原因 |
| --- | --- | --- | --- |
| prometheus-client | 0.22.1 | **0.26.0** | Python 3.13 环境下没有 0.22.1 的可用组合 |
| psutil | 7.0.0 | **7.2.2** | 同上 |
| fastapi | 0.115.12 | **0.141.1** | 同上 |
| uvicorn | 0.34.3 | **0.53.0** | 同上 |
| pytest | — | 9.1.1 | — |
| pyyaml | — | 6.0.3 | 用于校验 YAML 配置结构 |

`requirements.txt` 按 `pip freeze` 的**实际结果**写，不写推测版本。

**Prometheus 3.14.0 / Grafana 13.2.1 不是 pip 包**，是独立程序，
不在这份清单里。下载状态见下一节。

### 安装方式

直连 PyPI 实测约 100 KB/s 且频繁超时，最终用阿里云镜像：

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt `
  -i https://mirrors.aliyun.com/pypi/simple/ `
  --trusted-host mirrors.aliyun.com
```

`scripts/anzhuang.ps1` 已把这个镜像作为默认值。

---

## 五、★ 未实跑的部分（重要，如实记录）

### 5.1 Prometheus 与 Grafana 都没有跑起来

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 下载 Prometheus 3.x windows-amd64（约 100MB） | ❌ 未完成 | 本机约 100 KB/s，且 GitHub 下载被网络环境拦 |
| 下载 Grafana OSS（约 200MB） | ❌ 未下载 | 同上 |
| 启动 Prometheus、`/-/ready` 返回 200 | ❌ 未执行 | |
| `/targets` 看到 demo-app 是 UP | ❌ **未验证** | 实验 R5 未达成 |
| 在 Prometheus 里跑 PromQL 看返回值 | ❌ **未验证** | 实验 R6 未达成 |
| `promtool check config` / `check rules` | ❌ 未执行 | 缺 promtool |
| 启动 Grafana、数据源 Save & Test | ❌ **未验证** | 实验 R7 未达成 |
| 打开 Dashboard 看曲线 | ❌ **未看过** | — |
| 异常实验 A~D 的曲线变化 | ❌ **未观察** | 实验 R11 未达成 |

**因此本文件里没有任何"曲线符合预期"的断言。**
脚本（`scripts/fuzai.ps1`、`scripts/yichang-shiyan.ps1`）都已写好，
观察顺序也写清了，但**预期不等于实测**。

### 5.2 已经实跑并留证的

- 被监控应用真实运行，`/metrics` 输出真实指标（第二节有原始文本）
- 66 条 pytest 全部实跑通过
- 模板路由做标签、高基数控制、异常也计 5xx、在途数归零：真实执行的代码路径
- Windows 进程 CPU / 内存：psutil collector 真实输出
- 负载脚本的目标校验：真实执行并拒绝 `http://example.com`、`http://192.168.1.1:8000`

### 5.3 替代验证的覆盖程度

| 原本要靠 Prometheus 验证 | 替代方式 | 覆盖程度 |
| --- | --- | --- |
| `prometheus.yml` 合法 | PyYAML 结构校验（9 条） | 中 |
| 告警规则字段完整、有 for、有依据 | YAML 结构校验（含在 9 条里） | 中 |
| PromQL 写法正确 | 表达式静态校验（10 条） | 中 |
| Dashboard JSON 可用、单位/阈值/noValue 完整 | JSON 结构校验（14 条） | 中 |
| **曲线随负载变化** | **无替代** | **零** |

最后一行是最大的缺口，答辩时必须说明。

---

## 六、测试证据清单（对照实验要求）

| 要求的证据 | 在哪 |
| --- | --- |
| metrics 设计表和高基数检查 | `metrics-design.md`（第二节）+ `scripts/ceshi.ps1` 第 ③ ④ 步 |
| promtool / Compose 配置校验输出 | **未执行**（缺 promtool），替代：`test_peizhi.py` 9 条 |
| 异常时间线与 5 个关键 PromQL 结果 | `reports/timeline.md`（实验记录表，**未填真实数据**）、PromQL 见 `prometheus/alert-rules.yml` |
| Dashboard JSON / provisioning 与重启后截图 | `grafana/` 下三个文件（JSON + 两个 provisioning），**重启后截图未拍** |
| 可重复执行的测试命令 | `pytest -q` → 66 passed in 4.95s |
| 未实跑部分的边界 | 本文件第五节 + README 第六节 |

---

## 七、复现步骤

```powershell
git clone https://github.com/remchang/observability-platform
cd observability-platform
.\scripts\anzhuang.ps1        # 建 venv + 装依赖 + 检查工具 + 跑测试
.\scripts\qidong.ps1          # 起应用（有 Prometheus/Grafana 则一起起）
.\scripts\fuzai.ps1 -Moshi wending -Cishu 300
.\scripts\yichang-shiyan.ps1  # 四个异常实验
.\scripts\ceshi.ps1           # 全部测试 + 真实指标自检
```

**注意**：如果本机没装 Prometheus / Grafana，`qidong.ps1` 会给出下载地址并跳过，
只有应用会起来。这时候只能通过 `curl http://127.0.0.1:8000/metrics`
看原始指标，看不到 Dashboard。

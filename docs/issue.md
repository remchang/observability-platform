# Issue 清单（实验08）

> 仓库 Issue 正文留档。

---

## Issue #1 指标设计与高基数控制

**标签**：`设计`

### 从问题出发而不是从指标类型出发

指导书原文："从用户/运维问题出发设计 Dashboard，而不是从面板类型出发。"

所以先列问题，再选指标：

| 问题 | 指标 | 类型 |
| --- | --- | --- |
| 服务活着吗？ | `up` | Gauge（Prometheus 自带） |
| 应用自己觉得能服务吗？ | `app_up` | Gauge（应用主动置） |
| 有多少请求？ | `http_requests_total` | Counter |
| 快不快、有长尾吗？ | `http_request_duration_seconds` | Histogram |
| 吃了多少 CPU？ | `process_cpu_seconds_total` | Counter |
| 内存涨了吗？ | `process_resident_memory_bytes` | Gauge |
| 有积压吗？ | `app_in_flight_requests` | Gauge |

### ★ 高基数控制（本实验最重要的一条纪律）

标签只允许**有界集合**：`method` / `route`（模板路由）/ `status`。

**绝对禁止**：用户 ID、原始 URL、会话 ID、请求 ID、异常消息文本。

基数按乘积增长：`7 × 8 × 20 ≈ 1120`（可控）
vs 用原始 URL 时 `7 × 100000 × 20 = 1400 万`（必崩）。

### 验收条件

- [x] `metrics-design.md` 里每个指标都有名称/类型/单位/标签/桶/问题
- [x] `yuchuli_lu_you()` 取不到路由时返回固定字符串，**不回退到原始路径**
- [x] `yanchi_fen_tong()` 把毫秒归到 6 个桶名
- [x] 测试 `test_muban_luyou_kongzhi_jishu` 断言 3 个不同 ID 只产生 1 条序列
- [x] 测试 `test_404_...unmatched_er_bushi_yuanshi_lujing` 断言原始路径不进标签
- [x] 测试 `test_meiyou_gaojishi_biaoqian` 扫描所有 PromQL 禁止高基数标签
- [x] 真实 `/metrics` 输出证明 `route` 取值数 = 3（不是请求次数）

---

## Issue #2 应用埋点与 Windows 进程指标

**标签**：`核心功能`

### 埋点三条纪律

1. **用 `finally` 而不是 `except`**：异常请求也要计 5xx。
   只在正常路径计数的话，**服务开始报错时指标反而看不见错误**。
2. `/metrics` 自己不计入流量指标，否则每次抓取都多一次请求（自我污染）。
3. 路由值在 `call_next` **之后**取。

### ★ 为什么第 3 条是坑

第一版在 `call_next` 之前取 `request.scope["route"]`。
中间件包在应用外面，那时 Starlette **还没做路由匹配**，`scope["route"]` 是 `None`，
于是所有请求的 `route` 标签都是 `unmatched` —— 模板路由完全失效。

**代码不报错，而且序列数少得可疑地好看**，容易误以为"基数控制得很好"。
是测试 `test_qingqiu_jishu_zengjia` 报 `assert 0.0 == 1.0` 才暴露的。

### Windows 进程指标

`prometheus_client` 的 `ProcessCollector` 面向 Linux，
原生 Windows 上不提供 `process_cpu_seconds_total` 和
`process_resident_memory_bytes`。用 psutil 自建 collector，
**只在 win32 注册**（Linux 上会重名冲突）。

**口径必须写清**：这是**应用进程**，不是整机，也不是容器。

### 验收条件

- [x] 异常请求被计入 5xx（`test_500_cuowu_yie_ji_ru_jishu`）
- [x] `/metrics` 不被计入（`test_metrics_zishen_buji_ru_jishu`）
- [x] 在途请求数归零（`test_zai_tu_qingqiu_huifu_wei_ling`）
- [x] Histogram 有 `_bucket` 且含 `+Inf`（`test_histogram_bucket_cunzai`）
- [x] 真实输出 `process_cpu_seconds_total` / `process_resident_memory_bytes`
- [x] 500 响应不泄露堆栈（`test_500_xiangying_bu_baolu_duizhan`）

---

## Issue #3 Prometheus 抓取配置与告警规则

**标签**：`核心功能`

### 抓取配置

- `scrape_interval: 15s`，`scrape_timeout: 10s`（**必须 ≤ 间隔**，否则抓取重叠）
- 两个 job：`demo-app` 和 `prometheus` 自己（监控系统也要被监控）
- 目标写 `127.0.0.1:8000` 而不是 `localhost`（容器里 localhost 指向自己）
- 数据目录用启动参数指到项目内，不依赖系统默认路径

### ★ 9 条告警规则，每条都有「阈值依据」

指导书要求"先解释阈值来自何处"。做法是拿**正常基线**和
**受控实验能达到的水平**卡区间：

| 告警 | 正常 | 受控实验 | 阈值 | for |
| --- | --- | --- | --- | --- |
| 服务不可达 | up=1 | 停机 | up==0 | 1m（4 次抓取） |
| 5xx 错误率 | 0% | 50% | >5% | 2m |
| p95 延迟 | ~10ms | 500ms~2s | >1s | 3m |
| p50 延迟 | ~5ms | — | >300ms | 5m |
| 进程内存 | 60~90MB | — | >512MB | 5m |
| 进程 CPU | <0.2 核 | — | >0.8 核 | 5m |
| 抓取失败 | up=1 | 停机 | up==0 | 2m |
| 抓取变慢 | <1s | — | >5s | 3m |
| 规则评估失败 | 0 | — | >0 | 5m |

**全部带 `for`**。没有 `for` 的告警会被一次瞬时尖峰触发，
用不了多久就没人看了。

错误率还加了**分母保护**：`and sum(rate(...)) > 0.1`。
低流量时（1 分钟只有 2 个请求）一次 500 就能让比例冲到 50%。

### 验收条件

- [x] 配置结构校验 9 条（PyYAML）
- [x] 每条规则都有 `for`、`alert`、`expr`、`labels.yanzhong`、`annotations`
- [x] 每条规则的 `shuoming` 里都有阈值依据
- [x] `scrape_timeout <= scrape_interval`
- [x] 目标用 `127.0.0.1` 不是 `localhost`
- [x] 有 `up == 0` 可用性告警、有 `histogram_quantile` 延迟告警
- [ ] `promtool check` —— **未执行**（缺 promtool）

---

## Issue #4 自主设计 Grafana Dashboard

**标签**：`自主功能`

### ★ 明确不导入社区面板

指导书："现成面板导入不等于自主设计。"
`grafana/dashboards/` 下只有一个文件，是从零写的。

**10 个面板**，每个的 `description` 里都写了它回答什么运维问题：

① 服务是否在跑 ② 应用自报状态 ③ 5xx 错误率（带分母保护）
④ 请求速率（按路由） ⑤ 延迟分位数 p50/p95/p99 + 平均值对比
⑥ 状态码分布 ⑦ 进程 CPU ⑧ 进程内存 ⑨ 在途请求数 ⑩ 抓取耗时

**2 个模板变量**：`job`、`route`（多选）。

### 几个刻意的设计

| 设计 | 理由 |
| --- | --- |
| ⑤ 面板同时画 p50/p95/p99 **和平均值** | 让看的人直观看到"平均值会掩盖长尾" |
| ⑤ 面板阈值 1s 变红 | 和告警规则阈值一致，不一致会让人困惑 |
| ③ 面板带分母保护 | 低流量时显示"无流量"而不是误导性的高比例 |
| 所有面板都设 `noValue` | 没数据时要能区分"没数据"和"服务挂了" |
| 所有面板都设 `unit` | 不设单位的面板数字没有意义（"延迟 1.2"是什么单位？） |
| ⑩ 抓取耗时面板 | 预测性告警：接近超时是"即将抓不到"的前兆 |

### 验收条件

- [x] ≥5 个面板（实际 10 个）
- [x] 每个面板有 title + description + 非空 expr + unit + noValue
- [x] 有 p50/p95 分位数面板、有 up/CPU/内存面板
- [x] 数据源 uid 与 provisioning 一致
- [x] 有模板变量
- [x] 面板阈值与告警阈值一致（测试强制）
- [ ] 界面渲染 —— **未实跑**（Grafana 未安装）

---

## Issue #5 配置即代码（provisioning）

**标签**：`交付` `可复现`

### 为什么用 provisioning 而不是界面点

1. 界面配的存进 Grafana 数据库，换机器就没了；
2. 文件能进 Git、能被复核、能一键重建。

`allowUiUpdates: false` 是**刻意**的——否则会出现
"界面上改了、文件没变、换台机器就丢了"的经典问题。

数据源 `uid` 固定为 `prom-demo`（Dashboard JSON 引用的就是它）。

### 验收条件

- [x] 数据源 provisioning 文件（固定 uid、timeInterval 与抓取间隔一致）
- [x] Dashboard provisioning 文件（`allowUiUpdates: false`）
- [x] Dashboard JSON 入库
- [x] 测试断言面板引用的 uid 存在
- [x] 测试断言 `allowUiUpdates` 是 false
- [ ] 重启后验证 Dashboard 还在 —— **未实跑**

---

## Issue #6 受控异常实验与负载脚本

**标签**：`测试`

### 四种实验

| 实验 | 做法 | 观察 |
| --- | --- | --- |
| A 负载变化 | 300 请求 / 并发 4 | 请求速率、CPU、在途数 |
| B 延迟注入 | 交替打 `/api/slow?delay_ms=200~650` | **p95 上抬而 p50 变化小**（长尾） |
| C 错误注入 | 一半打 `/api/error?rate=1` | 错误率突破 5% |
| D 停机（手动） | 手停应用 | up 变 0，告警 Pending → Firing → Resolved |

### 安全约束

`jiancha_mubiao()` **写死只允许回环地址**。
传 `http://example.com`、`http://192.168.x.x` 直接拒绝。
这不是形式主义——避免误把线上地址粘进来压测。

受控延迟 `delay_ms` 限制 0~2000，防止被当成压测入口。

### 验收条件

- [x] 三种负载模式都有对应函数
- [x] 拒绝非本机目标（测试）
- [x] `delay_ms` / `rate` 越界返回 400（测试）
- [x] 发包函数**不抛异常**（失败也统计，不中断整批）
- [x] 500 连续触发后应用仍可用（测试）
- [x] `/healthz` 与业务解耦（测试）
- [ ] **曲线变化观察 —— 未实跑**

---

## Issue #7 ★ 环境限制：Prometheus / Grafana 未安装

**标签**：`限制` `如实记录`

### 情况

| 项 | 状态 |
| --- | --- |
| 下载 Prometheus（约 100MB） | ❌ 本机约 100KB/s，且 GitHub 下载被网络环境拦 |
| 下载 Grafana（约 200MB） | ❌ 未下载 |
| 启动、抓取、PromQL、Dashboard、曲线 | ❌ **全部未执行** |

### 处理方式

1. **不编造任何"曲线符合预期"的结论。**
2. 把原本要靠 Prometheus 验证的东西尽量用**静态校验**替代：
   配置 9 条、PromQL 10 条、Dashboard 14 条。
3. 明确标出替代验证的覆盖程度，特别是
   **"曲线随负载变化"这一项覆盖程度为零**。
4. 把 Prometheus/Grafana 的下载与启动写进脚本，别人可以一键补上。

### 教训

这已经是**第三次**因为在写代码之前没确认环境而返工（实验03、07、08）。
**环境确认应该是第 0 步**，不是写完代码之后的第 1 步。

---

## Issue #8 测试与交付文档

**标签**：`测试` `文档`

### 交付

- [x] 66 条 pytest（指标 14 / 配置 9 / PromQL 10 / Dashboard 14 / 异常 13）
- [x] `metrics-design.md` 指标设计表（含高基数说明与盲区表）
- [x] `README.md`（Mermaid 架构图、命令、已知限制、思考题）
- [x] `docs/实验报告.md`、`docs/ceshi-jilu.md`
- [x] `NOTICE.md`（**含 Grafana AGPL 义务说明**）
- [x] `scripts/`：安装 / 启动 / 负载 / 异常实验 / 测试
- [x] **真实 `/metrics` 输出证据**（不是构造的）

### 已知缺口

- Prometheus / Grafana 未实跑，"曲线变化"无任何证据
- 未做 SLO / Error Budget 面板
- 未做日志与追踪关联
- 单 worker 限制

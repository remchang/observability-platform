# 第三方资源与许可证说明（NOTICE）

本仓库是《开源软件与新技术》课程实验08 的**二次开发成品**。

---

## ⚠️ 关于 Grafana 的 AGPL-3.0（重要，单独提醒）

**Grafana OSS 使用 AGPL-3.0 许可证**，这是本实验里唯一一个强 copyleft 的组件。

| 情况 | 义务 |
| --- | --- |
| 本地个人使用、不分发 | 无额外义务 |
| **通过网络提供服务**（AGPL 的"网络条款"） | **必须**向使用者提供完整源代码，包括你对它的修改 |
| 分发二进制 | 必须附许可证全文与源码提供方式 |

本实验只是在**本机**运行 Grafana 用于课程演示，不分发也不对外提供服务，
所以目前没有触发额外义务。但**如果以后把这个监控平台对外部署**，
就必须：

1. 在界面上保留 Grafana 的版权与许可证声明；
2. 提供 Grafana 对应版本的完整源码（或可获取的下载地址）；
3. 对你修改过的部分同样开放源码。

指导书也专门写了这一点："AGPL 项目的网络部署版本尤其应保留许可证与源码提供义务说明。"

**注意区分**：`prometheus-client`（Python 客户端库）是 **Apache-2.0**，
和 Grafana 的 AGPL 完全无关，不要混为一谈。

---

## 一、上游项目

| 项目 | 用途 | 版本 | 许可证 | 本次使用程度 |
| --- | --- | --- | --- | --- |
| [prometheus/prometheus](https://github.com/prometheus/prometheus) | 指标抓取、存储与 PromQL 查询 | 3.x（下载未完成） | Apache-2.0 | **未实跑**（见说明） |
| [grafana/grafana](https://github.com/grafana/grafana) | 可视化与 Dashboard | 13.x（未下载） | **AGPL-3.0** | **未实跑** |
| [prometheus/client_python](https://github.com/prometheus/client_python) | 暴露 `/metrics` | 0.26.0 | Apache-2.0 | **已装、已实跑** |
| [giampaolo/psutil](https://github.com/giampaolo/psutil) | 补 Windows 进程指标 | 7.2.2 | BSD-3-Clause | **已装、已实跑** |
| [fastapi/fastapi](https://github.com/fastapi/fastapi) | 被监控应用框架 | 见 requirements | MIT | 已装、已实跑 |
| [encode/uvicorn](https://github.com/encode/uvicorn) | ASGI 服务器 | 见 requirements | BSD-3-Clause | 已装 |
| [pytest-dev/pytest](https://github.com/pytest-dev/pytest) | 测试框架 | 9.1.1 | MIT | 已装、66 条测试实跑通过 |
| [yaml/pyyaml](https://github.com/yaml/pyyaml) | 校验 YAML 配置结构 | 6.0.3 | MIT | 已装 |

## 二、上游提供的能力 vs 本人实现的部分

| 能力 | 谁提供的 |
| --- | --- |
| 抓取模型、时序存储、PromQL 引擎、告警规则执行 | **上游 Prometheus** |
| 数据源连接、面板渲染、变量、阈值着色 | **上游 Grafana** |
| `Counter` / `Gauge` / `Histogram` 类型与 `/metrics` 文本格式 | **上游 prometheus-client** |
| 应用埋点（中间件、指标选型、标签设计） | **本人实现**（`app/zhibiao.py`、`app/main.py`） |
| 指标设计表（问题 → 指标 → 单位 → 标签 → 桶） | **本人编写**（`metrics-design.md`） |
| 高基数控制的实现与强制（模板路由、分桶标签） | **本人实现** + 4 条测试 |
| Windows 进程指标补充 collector | **本人实现**（`WindowsJinchengZhibiao`） |
| Prometheus 抓取配置与 9 条告警规则（含阈值依据） | **本人编写**（`prometheus/`） |
| **自主设计的 Dashboard（10 个面板 + 2 个变量）** | **本人设计**（`grafana/dashboards/ziyuan-yunxing.json`） |
| Grafana provisioning 配置 | **本人编写** |
| 受控负载脚本（三种模式） | **本人实现**（`fuwu/fuzai.py`） |
| 66 条测试 | **本人编写**（`tests/`） |

**没有导入任何社区 Dashboard。** 指导书写得很清楚：
"现成面板导入不等于自主设计"。`grafana/dashboards/` 下只有一个文件，
是本人从零写的，每个面板的 `description` 里都写了它回答什么运维问题。
测试 `test_meige_mianban_dou_shuoming_ta_huida_de_wenti` 强制检查这一点。

## 三、★ 关于"未实跑 Prometheus / Grafana"

| 项 | 状态 |
| --- | --- |
| 下载 Prometheus 3.x windows-amd64（约 100MB） | ❌ 未完成（本机网络约 100 KB/s，超时） |
| 下载 Grafana OSS（约 200MB） | ❌ 未下载 |
| 启动 Prometheus daemon | ❌ 未执行 |
| 在 `/targets` 看到 UP | ❌ 未执行 |
| 在 Prometheus 里执行 PromQL | ❌ 未执行 |
| 启动 Grafana 并连接数据源 | ❌ 未执行 |
| 看 Dashboard 曲线 | ❌ 未执行 |
| `promtool check config` / `check rules` | ❌ 未执行（promtool 在 Prometheus 包里） |

**已经实跑并留证的**：

- 被监控应用真实运行，`/metrics` 输出真实指标（有原始文本证据）
- **66 条测试全部通过**，其中包含对真实指标输出的断言
- 模板路由做标签、高基数控制、异常也计 5xx：都是真实执行的代码路径
- Windows 进程 CPU/内存指标：通过 psutil collector 真实输出

**未实跑的部分**在 README、实验报告、测试记录里都标明了，
**没有任何"曲线符合预期"的编造断言**。

## 四、数据来源

`app/main.py` 里的 20 条商品是虚构的演示数据，不含任何真实业务信息。

## 五、本仓库自己的许可证

**MIT**，见 [LICENSE](LICENSE)。

与上游许可证的兼容性：

| 上游 | 许可证 | 与 MIT 兼容 |
| --- | --- | --- |
| Prometheus | Apache-2.0 | ✅ |
| prometheus-client | Apache-2.0 | ✅ |
| psutil / FastAPI / pytest / PyYAML | MIT / BSD | ✅ |
| **Grafana** | **AGPL-3.0** | ⚠️ **不兼容**——所以本仓库**不包含也不分发** Grafana 的任何代码，只在文档里给出下载地址 |

最后一行很关键：**AGPL 与 MIT 不兼容**，所以本仓库绝对不能
把 Grafana 的代码或二进制打包进来。只能在文档里写下载方式。

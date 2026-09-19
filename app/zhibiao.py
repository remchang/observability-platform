# -*- coding: utf-8 -*-
"""
zhibiao.py —— 指标定义集中在这里。

为什么单独一个文件：指标名、类型、标签、桶边界是"设计决策"，
散落在各个路由里就没人能一眼看清全貌。设计表见 metrics-design.md。

★ 高基数控制（本实验最重要的纪律）：
    标签只允许用**有界集合**：
      method  —— GET / POST / ... 就那几个
      route   —— 模板路由（/api/items/{id}），**不是**原始 URL
      status  —— HTTP 状态码，数量有限
    绝对不能用：用户 ID、原始 URL、查询参数、异常消息文本。
    这些东西的取值数量会随流量无限增长，Prometheus 的内存和查询都会被打爆。
"""
import sys

from prometheus_client import Counter, Gauge, Histogram, REGISTRY
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

# ---------------- HTTP 指标 ----------------

# 请求计数。用 Counter：只增不减，重启会重置（rate() 能正确处理重置）
HTTP_QINGQIU_ZONGSHU = Counter(
    "http_requests_total",
    "HTTP 请求总数",
    ["method", "route", "status"],
)

# 请求延迟分布。用 Histogram 而不是平均值——
# 平均值会把"少数很慢的请求"平均掉，看不出长尾。
# 分位数必须从 _bucket 算（histogram_quantile），这是 Prometheus 的标准做法。
HTTP_YANCHI = Histogram(
    "http_request_duration_seconds",
    "HTTP 请求耗时（秒）",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)

# 应用自报的状态。Gauge 可增可减，适合表示"当前值"。
# 用它来实现"服务主动说不健康"（比如依赖挂了），比只看 up 更细。
YINGYONG_ZHUANGTAI = Gauge(
    "app_up",
    "应用自身状态：1=正常，0=异常",
)

# 当前正在处理的请求数。用来观察并发压力，也是 Gauge。
ZHENGZAI_CHULI = Gauge(
    "app_in_flight_requests",
    "当前正在处理的请求数",
)

# 受控延迟的注入次数（异常实验用）。带 method/route 有界标签。
YANCHI_ZHURU = Counter(
    "app_injected_delay_total",
    "受控延迟注入次数（异常实验用）",
    ["route", "delay_ms_bucket"],
)


# ---------------- Windows 进程指标补充 ----------------

class WindowsJinchengZhibiao:
    """
    原生 Windows 上 prometheus_client 的 ProcessCollector **不提供**
    process_cpu_seconds_total 和 process_resident_memory_bytes
    （它是面向 Linux 的）。所以这里用 psutil 自己补一个 collector。

    ★ 口径说明（很容易搞混，报告里也写了）：
        这里量的是**当前应用进程**，不是整机 CPU/内存。
        整机的要用 node_exporter，容器内的要用 cAdvisor，
        三种口径不能混着画在同一张图上比较。
    """

    def collect(self):
        try:
            import psutil
        except ImportError:
            # 没装 psutil 就不输出，不要让整个 /metrics 挂掉
            return

        jincheng = psutil.Process()
        shijian = jincheng.cpu_times()

        yield CounterMetricFamily(
            "process_cpu_seconds",
            "进程累计 CPU 时间（秒）",
            value=shijian.user + shijian.system,
        )
        yield GaugeMetricFamily(
            "process_resident_memory_bytes",
            "进程常驻内存 RSS（字节）",
            value=jincheng.memory_info().rss,
        )
        # 顺便暴露 fd/句柄数，Windows 上也有信息
        try:
            yield GaugeMetricFamily(
                "process_open_fds",
                "进程打开的句柄数",
                value=jincheng.num_handles() if sys.platform == "win32"
                else jincheng.num_fds(),
            )
        except Exception:            # noqa: BLE001
            pass


def zhuce_windows_buchong():
    """
    只在 Windows 上注册补充 collector。

    为什么单独写个函数、还只在 win32 注册：
      Linux 上默认的 ProcessCollector 已经提供了这两个名字，
      再注册一次会冲突（重复的时间序列）。
      所以必须按平台区分，不能无脑注册。
    """
    if sys.platform != "win32":
        return False
    try:
        REGISTRY.register(WindowsJinchengZhibiao())
        return True
    except ValueError:
        # 已经注册过了，忽略
        return False


def qu_yuzhi_tongji(lu_you, fangfa):
    """测试用：直接读某个标签组合的计数值，不用去解析 /metrics 文本。"""
    return HTTP_QINGQIU_ZONGSHU.labels(method=fangfa, route=lu_you, status="200")


def yuchuli_lu_you(request):
    """
    从请求里取"模板路由"当作标签值。

    为什么不能直接用 request.url.path：
        /api/items/1 和 /api/items/2 会被当成两个不同的标签值，
        取值的数量随数据量线性增长 —— 这就是典型的高基数爆炸。

    Starlette 会把匹配到的路由放在 request.scope["route"] 里，
    它的 .path 是模板形式（/api/items/{item_id}），取值数量有限。
    """
    route = request.scope.get("route")
    if route is None:
        # 没匹配到任何路由（404），统一归到 unmatched，不用原始路径
        return "unmatched"
    return getattr(route, "path", "unmatched")


def yanchi_fen_tong(haomiao):
    """
    把延迟值归到有限的桶名里，**不要把具体的毫秒数当标签**。
    比如传 500ms 和 501ms 归到同一个 "500-750" 桶。
    """
    try:
        hao = int(haomiao)
    except (TypeError, ValueError):
        return "unknown"
    if hao <= 0:
        return "0"
    if hao <= 50:
        return "1-50"
    if hao <= 200:
        return "51-200"
    if hao <= 500:
        return "201-500"
    if hao <= 1000:
        return "501-1000"
    return "1000+"

# -*- coding: utf-8 -*-
"""
test_zhibiao.py —— 指标单元 / 集成测试（实验要求 ≥6 条）。

重点验证三件事：
  ① Counter / Histogram / Gauge 的语义正确（只增、会观察、可增可减）
  ② **异常请求也计入 5xx**（这是最容易被漏掉的一条）
  ③ 标签基数受控：模板路由做标签，原始 URL 绝不能进去
"""
from conftest import qu_jishu, qu_yanchi_cishu, qu_zhibiao_wenben


def test_qingqiu_jishu_zengjia(kehu):
    """Counter 语义：请求一次，计数加一。"""
    qian = qu_jishu("/api/items", "GET", "200")
    r = kehu.get("/api/items")
    assert r.status_code == 200
    hou = qu_jishu("/api/items", "GET", "200")
    assert hou == qian + 1


def test_yanchi_beiguancha(kehu):
    """Histogram 语义：每次请求都会 observe 一次，count 递增。"""
    qian = qu_yanchi_cishu("/api/items", "GET")
    kehu.get("/api/items")
    kehu.get("/api/items")
    hou = qu_yanchi_cishu("/api/items", "GET")
    assert hou == qian + 2


def test_metrics_zishen_buji_ru_jishu(kehu):
    """/metrics 自己不能被计入流量指标，否则每次抓取都多一次请求，自我污染。"""
    qian = qu_jishu("/metrics", "GET", "200")
    for _ in range(3):
        kehu.get("/metrics")
    hou = qu_jishu("/metrics", "GET", "200")
    assert hou == qian, "抓 /metrics 被计入了请求数"


def test_500_cuowu_yie_ji_ru_jishu(kehu):
    """
    ★ 实验要求："在 try/finally 中记录业务异常的 5xx 状态"。
    受控错误接口会抛异常 → 中间件必须在 finally 里把它计成 500。
    如果只在正常路径计数，服务开始报错时指标反而"看不见错误"。
    """
    qian = qu_jishu("/api/error", "GET", "500")
    r = kehu.get("/api/error?rate=1")
    assert r.status_code == 500
    hou = qu_jishu("/api/error", "GET", "500")
    assert hou == qian + 1, "异常请求没有被计入 5xx"


def test_404_biao_ji_wei_unmatched_er_bushi_yuanshi_lujing(kehu):
    """
    ★ 高基数控制：没匹配到路由的请求，标签值必须是 unmatched，
    不能是原始路径（否则攻击者扫一堆不存在的路径就能把标签基数打爆）。
    """
    qian = qu_jishu("unmatched", "GET", "404")
    kehu.get("/zhege/lujing/bucunzai/abcdefg123")
    hou = qu_jishu("unmatched", "GET", "404")
    assert hou == qian + 1

    # 确认原始路径没有被当成标签值
    wenben = qu_zhibiao_wenben(kehu)
    assert "abcdefg123" not in wenben, "原始 URL 进了标签，高基数风险"


def test_muban_luyou_kongzhi_jishu(kehu):
    """
    ★ 这是本实验最关键的一条高基数测试。
    访问 /api/items/1 和 /api/items/2 必须产生**同一个** route 标签
    （/api/items/{item_id}），而不是两条时间序列。
    """
    qian = qu_jishu("/api/items/{item_id}", "GET", "200")
    kehu.get("/api/items/1")
    kehu.get("/api/items/2")
    kehu.get("/api/items/3")
    hou = qu_jishu("/api/items/{item_id}", "GET", "200")
    assert hou == qian + 3, "三个不同 ID 没有归到同一个模板路由"

    wenben = qu_zhibiao_wenben(kehu)
    # 序列里不该出现具体 ID 形式的 route 标签
    assert 'route="/api/items/1"' not in wenben
    assert 'route="/api/items/2"' not in wenben


def test_yingyong_zhuangtai_gauge_ke_bian(kehu):
    """Gauge 语义：可增可减，适合表示"当前状态"。"""
    kehu.get("/healthz")
    wenben = qu_zhibiao_wenben(kehu)
    assert "app_up" in wenben
    assert "app_in_flight_requests" in wenben


def test_zai_tu_qingqiu_huifu_wei_ling(kehu):
    """在途请求数在请求结束后必须回到 0，否则说明中间件没有成对增减。"""
    for _ in range(5):
        kehu.get("/api/items")
    from prometheus_client import REGISTRY
    zhi = REGISTRY.get_sample_value("app_in_flight_requests")
    assert zhi == 0.0, "在途请求数没有归零，中间件的 inc/dec 不成对"


def test_histogram_bucket_cunzai(kehu):
    """
    Histogram 必须有 _bucket 序列，否则 histogram_quantile 算不出来。
    这是 Dashboard 上 p95 面板能不能出数的前提。
    """
    kehu.get("/api/items")
    wenben = qu_zhibiao_wenben(kehu)
    assert "http_request_duration_seconds_bucket" in wenben
    assert "http_request_duration_seconds_count" in wenben
    assert "http_request_duration_seconds_sum" in wenben
    # 必须有 +Inf 桶，否则分位数计算会缺最后一段
    assert 'le="+Inf"' in wenben


def test_metrics_content_type_wanzheng(kehu):
    """Content-Type 要带 version 参数，有些采集端会校验。"""
    x = kehu.get("/metrics")
    assert "text/plain" in x.headers["content-type"]
    assert "version=" in x.headers["content-type"]


def test_yanchi_zhuru_you_bianjie_biaoqian(kehu):
    """
    受控延迟的计数里，延迟值也必须是**分桶名**而不是具体毫秒数，
    否则每个不同的 delay_ms 都会产生一条新序列。
    """
    kehu.get("/api/slow?delay_ms=500")
    kehu.get("/api/slow?delay_ms=501")
    wenben = qu_zhibiao_wenben(kehu)
    assert 'delay_ms_bucket="201-500"' in wenben
    assert 'delay_ms_bucket="501"' not in wenben


def test_slow_canshu_yuejie_400(kehu):
    """受控延迟必须限制范围，不能变成压测入口。"""
    assert kehu.get("/api/slow?delay_ms=5000").status_code == 400
    assert kehu.get("/api/slow?delay_ms=-1").status_code == 400
    assert kehu.get("/api/slow?delay_ms=0").status_code == 200


def test_500_xiangying_bu_baolu_duizhan(kehu):
    """★ 500 响应体不能带异常原文，否则泄露内部结构。"""
    x = kehu.get("/api/error?rate=1")
    ti = x.json()
    assert x.status_code == 500
    assert "这是受控制造的" not in x.text
    assert "Traceback" not in x.text
    assert "受控制造" not in x.text

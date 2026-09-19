# -*- coding: utf-8 -*-
"""
test_promql.py —— PromQL 测试（实验要求 ≥6 条）。

★ 诚实说明：本机**没有安装 Prometheus**，所以没法真的把查询发给
   /api/v1/query 看返回值。这一组做的是**表达式静态校验**：
   检查 PromQL 的写法有没有踩常见坑。

   它能抓到的问题都是真实会犯的：
     · Counter 直接画原值（应该用 rate）
     · histogram_quantile 少了 sum by (le)
     · 错误率没有分母保护，低流量时除零或剧烈抖动
     · 用了原始 URL 或用户 ID 当标签（高基数）
     · 时间窗口写错单位
"""
import os
import re

import pytest
import yaml

GEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROM = os.path.join(GEN, "prometheus")
DASH = os.path.join(GEN, "grafana", "dashboards", "ziyuan-yunxing.json")


def _suoyou_biaodashi():
    """把告警规则和 Dashboard 里所有的 PromQL 表达式收集起来，带出处。"""
    jieguo = []
    with open(os.path.join(PROM, "alert-rules.yml"), "r", encoding="utf-8") as f:
        guize = yaml.safe_load(f)
    for zu in guize["groups"]:
        for r in zu.get("rules", []):
            jieguo.append(("alert:" + r["alert"], r["expr"]))

    import json
    with open(DASH, "r", encoding="utf-8") as f:
        db = json.load(f)
    for p in db["panels"]:
        for t in p.get("targets", []):
            if t.get("expr"):
                jieguo.append(("panel:" + p["title"], t["expr"]))
    return jieguo


BIAODASHI = _suoyou_biaodashi()


def test_biaodashi_shuliang():
    assert len(BIAODASHI) >= 10, "表达式太少，覆盖不够"


def test_counter_bixu_yong_rate_huo_increase():
    """
    ★ Counter 是累计值，直接画原值只能得到一条一路向上的线，
    除了"重启会掉下来"之外看不出任何东西。必须包一层 rate()/increase()。
    """
    wenti = []
    for laiyuan, biao in BIAODASHI:
        if "http_requests_total" in biao and "http_request_duration" not in biao:
            if "rate(" not in biao and "increase(" not in biao:
                wenti.append(laiyuan)
    assert wenti == [], "这些表达式直接用了 Counter 原值：%s" % wenti


def test_process_cpu_bixu_yong_rate():
    """process_cpu_seconds_total 也是 Counter，必须 rate()。"""
    wenti = []
    for laiyuan, biao in BIAODASHI:
        if "process_cpu_seconds_total" in biao and "rate(" not in biao:
            wenti.append(laiyuan)
    assert wenti == [], wenti


def test_histogram_quantile_bixu_you_sum_by_le():
    """
    ★ histogram_quantile 少了 `sum by (le)` 会算错。
    因为分位数必须按桶聚合，聚合时保留 le 标签才有意义。
    """
    wenti = []
    for laiyuan, biao in BIAODASHI:
        if "histogram_quantile" in biao:
            if "sum by (le)" not in biao and "sum by(le)" not in biao:
                wenti.append(laiyuan)
    assert wenti == [], "这些表达式缺 sum by (le)：%s" % wenti


def test_histogram_quantile_yong_bucket_zhibiao():
    """分位数必须作用在 _bucket 上，不是 _count 或 _sum。"""
    for laiyuan, biao in BIAODASHI:
        if "histogram_quantile" in biao:
            assert "_bucket" in biao, "%s 没有用 _bucket" % laiyuan


def test_cuowu_lv_you_fenmu_baohu():
    """
    ★ 错误率必须有分母保护（`and sum(rate(...)) > 阈值`）。
    没有保护的话，低流量时（比如 1 分钟只有 2 个请求）分母很小，
    一次 500 就能让比例冲到 50%，告警疯狂抖动。
    """
    for laiyuan, biao in BIAODASHI:
        if "status=~\"5..\"" in biao and "/" in biao:
            assert re.search(r"\band\b", biao), \
                "%s 的错误率没有分母保护，低流量时会剧烈抖动" % laiyuan


def test_shijian_chuangkou_danwei_hefa():
    """所有 [Nx] 窗口的单位必须是 s/m/h/d/w/y。"""
    hefa = set("smhdwy")
    for laiyuan, biao in BIAODASHI:
        for chuang in re.findall(r"\[(\d+)([a-z]+)\]", biao):
            assert chuang[1] in hefa, "%s 的时间单位不对：%s" % (laiyuan, chuang[1])
            assert int(chuang[0]) > 0


def test_shijian_chuangkou_buyao_guoduan():
    """
    窗口太短（< 30s）在 15s 抓取间隔下只有 2 个样本，
    rate() 的外推会算得很不准。
    """
    suoxie = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    wenti = []
    for laiyuan, biao in BIAODASHI:
        for n, dan in re.findall(r"\[(\d+)([smhd])\]", biao):
            if int(n) * suoxie[dan] < 30:
                wenti.append("%s [%s%s]" % (laiyuan, n, dan))
    assert wenti == [], "窗口太短：%s" % wenti


def test_meiyou_gaojishi_biaoqian():
    """
    ★ 高基数控制：表达式里不能出现用户 ID / 原始 URL / 邮箱这类标签。
    这些标签的取值数量随流量无限增长，会把 Prometheus 打爆。
    """
    weixian = ("user_id", "userid", "uid=", "email", "session", "url=",
               "path=", "request_id", "trace_id")
    wenti = []
    for laiyuan, biao in BIAODASHI:
        di = biao.lower()
        for w in weixian:
            if w in di and w != "uid=":      # 排除 datasource uid 的误判
                wenti.append("%s 含 %s" % (laiyuan, w))
    assert wenti == [], "疑似高基数标签：%s" % wenti


def test_you_up_chaxun():
    """必须有 up 查询——它是最基础的可用性依据，且不依赖应用埋点。"""
    zhaodao = any(re.search(r"\bup\b", b) for _, b in BIAODASHI)
    assert zhaodao


def test_you_p95_chaxun():
    zhaodao = any("histogram_quantile(0.95" in b or "0.95" in b for _, b in BIAODASHI)
    assert zhaodao


def test_zhibiao_ming_dou_zai_biaodashi_li_chuxian_guo():
    """
    埋点里定义的五类指标，至少要能在某个查询里找到——
    否则就是"埋了但没人看"，或者"面板查了不存在的指标"。
    """
    quanwen = " ".join(b for _, b in BIAODASHI)
    for ming in ("http_requests_total", "http_request_duration_seconds",
                 "app_up", "process_cpu_seconds_total",
                 "process_resident_memory_bytes"):
        assert ming in quanwen, "指标 %s 没有出现在任何查询里" % ming

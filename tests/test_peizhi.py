# -*- coding: utf-8 -*-
"""
test_peizhi.py —— 配置测试（实验要求 ≥3 条）。

本机没有 promtool（Prometheus 未安装），所以这里用 PyYAML 做**结构校验**：
字段在不在、取值合不合理、规则文件能不能对上。

★ 这不能替代 promtool，但能抓到几类实际会犯的错：
   · 抓取目标写成 localhost（容器里会指向自己）
   · 告警规则缺 for（一次尖峰就告警）
   · rule_files 指向不存在的文件
   · 抓取间隔写成非法值
"""
import os

import pytest
import yaml

GEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROM = os.path.join(GEN, "prometheus")


def du_yaml(ming):
    with open(os.path.join(PROM, ming), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def prom_peizhi():
    return du_yaml("prometheus.yml")


@pytest.fixture(scope="module")
def guize():
    return du_yaml("alert-rules.yml")


def test_prometheus_yml_jiegou(prom_peizhi):
    assert "global" in prom_peizhi
    assert "scrape_configs" in prom_peizhi
    assert len(prom_peizhi["scrape_configs"]) >= 1


def test_zhuaqu_jiange_hefa(prom_peizhi):
    """抓取间隔必须是合法的时长字符串，不能是数字或空。"""
    g = prom_peizhi["global"]
    for jian in ("scrape_interval", "evaluation_interval", "scrape_timeout"):
        zhi = g.get(jian)
        assert isinstance(zhi, str), "%s 必须是字符串（如 15s）" % jian
        assert zhi[-1] in "smhd", "%s 结尾要是时间单位" % jian


def test_chaoshi_xiaoyu_jiange(prom_peizhi):
    """
    抓取超时必须小于等于抓取间隔。
    超时比间隔还长的话，下一次抓取会和上一次重叠，行为不可预测。
    """
    g = prom_peizhi["global"]
    zhi = lambda s: int(s.rstrip("smhd")) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[s[-1]]
    assert zhi(g["scrape_timeout"]) <= zhi(g["scrape_interval"])


def test_mubiao_yong_huiluo_dizhi_bushi_localhost(prom_peizhi):
    """
    ★ 原生 Windows 路线必须写 127.0.0.1；
      如果写 localhost，在容器路线下会指向容器自己（最常见的一个坑）。
    这里断言本配置用的是 127.0.0.1，并且注释里写清了容器路线该用什么。
    """
    zhaodao = False
    for job in prom_peizhi["scrape_configs"]:
        for sc in job.get("static_configs", []):
            for t in sc.get("targets", []):
                if "8000" in str(t):
                    assert str(t).startswith("127.0.0.1:"), \
                        "应用目标应该用 127.0.0.1，不要用 localhost"
                    zhaodao = True
    assert zhaodao, "没有找到指向应用的抓取目标"


def test_rule_files_zhi_xiang_cunzai_de_wenjian(prom_peizhi):
    """rule_files 指向的文件必须真实存在，否则 Prometheus 启动会报错。"""
    for p in prom_peizhi.get("rule_files", []):
        quang = os.path.join(PROM, p)
        assert os.path.exists(quang), "rule_files 指向的文件不存在：%s" % p


def test_guize_wenjian_jiegou(guize):
    assert "groups" in guize
    assert len(guize["groups"]) >= 3, "告警分组太少，覆盖不全"


def test_meitiao_guize_dou_you_for(guize):
    """
    ★ 实验要求："设计一条有 for 持续时间的告警"。
    这里把要求升级成"**每条**都必须有 for"——
    没有 for 的告警会被一次瞬时尖峰触发，用不了多久就没人看了。
    """
    queshao = []
    for zu in guize["groups"]:
        for r in zu.get("rules", []):
            if "for" not in r:
                queshao.append(r.get("alert"))
    assert queshao == [], "这些告警缺 for：%s" % queshao


def test_meitiao_guize_ziduan_wanzheng(guize):
    """每条规则必须有 alert / expr / labels.yanzhong / annotations 三项说明。"""
    for zu in guize["groups"]:
        for r in zu.get("rules", []):
            assert r.get("alert"), "有规则没有 alert 名字"
            assert isinstance(r.get("expr"), str) and r["expr"].strip(), \
                "%s 的 expr 是空的" % r.get("alert")
            assert r.get("labels", {}).get("yanzhong") in (
                "xinxi", "jinggao", "yanzhong"), \
                "%s 的严重级别不在约定集合里" % r.get("alert")
            ann = r.get("annotations", {})
            assert ann.get("zhaiyao"), "%s 缺 zhaiyao" % r.get("alert")
            assert ann.get("shuoming"), "%s 缺 shuoming（要解释阈值依据）" % r.get("alert")


def test_gaojing_shuoming_li_you_tiaojian_yiju(guize):
    """
    ★ 实验要求："先解释阈值来自何处"。
    所以每条告警的 shuoming 里必须出现能说明依据的关键词。
    """
    guanjian = ("依据", "因为", "来自", "正常", "基线", "阈值", "持续", "窗口")
    queshao = []
    for zu in guize["groups"]:
        for r in zu.get("rules", []):
            shuo = (r.get("annotations") or {}).get("shuoming", "")
            if not any(k in shuo for k in guanjian):
                queshao.append(r.get("alert"))
    assert queshao == [], "这些告警没写阈值依据：%s" % queshao


def test_for_shichang_dou_shimiao_jibie(guize):
    """for 的时长应该是秒/分钟级别，不能出现 1d 这种（等于不会告警）。"""
    for zu in guize["groups"]:
        for r in zu.get("rules", []):
            fo = r["for"]
            assert fo[-1] in "sm", "%s 的 for 太长：%s" % (r["alert"], fo)


def test_you_keyongxing_gaojing(guize):
    """必须有 up == 0 这条最基本的可用性告警。"""
    zhaodao = False
    for zu in guize["groups"]:
        for r in zu.get("rules", []):
            if "up" in r["expr"] and "== 0" in r["expr"]:
                zhaodao = True
    assert zhaodao, "缺少服务不可用告警（up == 0）"


def test_you_p95_yanchi_gaojing(guize):
    """必须有基于 histogram_quantile 的延迟告警。"""
    zhaodao = False
    for zu in guize["groups"]:
        for r in zu.get("rules", []):
            if "histogram_quantile" in r["expr"]:
                zhaodao = True
    assert zhaodao, "缺少延迟分位数告警"

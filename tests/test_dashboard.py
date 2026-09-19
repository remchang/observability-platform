# -*- coding: utf-8 -*-
"""
test_dashboard.py —— Dashboard 测试（实验要求 ≥6 条）。

★ 关键立场（指导书明确要求）：
    "Dashboard 必须显示当前服务/环境和无数据状态，不能直接导入一个
     不理解的社区 Dashboard。"
    "现成面板导入不等于自主设计。"

所以这一组不只是"JSON 能不能解析"，还检查：
    · 每个面板有没有写清它回答的问题（description）
    · 单位设了没有（不设单位的面板数字没有意义）
    · 无数据状态有没有提示（noValue）
    · 阈值和告警规则一致不一致
    · 面板里引用的数据源 uid 和 provisioning 里的一致不一致
"""
import json
import os
import re
import yaml

GEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASH_LU = os.path.join(GEN, "grafana", "dashboards", "ziyuan-yunxing.json")
DS_LU = os.path.join(GEN, "grafana", "provisioning", "datasources", "prometheus.yml")
DB_LU = os.path.join(GEN, "grafana", "provisioning", "dashboards", "dashboards.yml")


def du_dashboard():
    with open(DASH_LU, "r", encoding="utf-8") as f:
        return json.load(f)


def test_dashboard_json_hefa():
    db = du_dashboard()
    assert db["title"]
    assert isinstance(db["panels"], list)


def test_mianban_shuliang_bu_shao_yu_wu():
    """实验要求"至少 5 个面板"。这里做了 10 个。"""
    db = du_dashboard()
    assert len(db["panels"]) >= 5, "面板只有 %d 个" % len(db["panels"])


def test_meige_mianban_dou_you_biaoti():
    db = du_dashboard()
    for p in db["panels"]:
        assert p.get("title"), "有面板没标题"


def test_meige_mianban_dou_shuoming_ta_huida_de_wenti():
    """
    ★ 自主设计的核心证据：每个面板都要写清楚"它回答什么问题"。
    没有 description 的面板，别人（包括三个月后的自己）看不懂为什么要有它。
    """
    queshao = [p.get("title") for p in du_dashboard()["panels"]
               if not (p.get("description") or "").strip()]
    assert queshao == [], "这些面板没写 description：%s" % queshao


def test_meige_mianban_dou_you_feikong_chaxun():
    db = du_dashboard()
    for p in db["panels"]:
        mubiao = [t for t in p.get("targets", []) if (t.get("expr") or "").strip()]
        assert mubiao, "%s 没有有效查询" % p.get("title")


def test_meige_mianban_dou_she_le_danwei():
    """
    不设单位的面板，数字是没有意义的：
    "延迟 1.2" 到底是 1.2 秒还是 1.2 毫秒？没法判断。
    """
    queshao = []
    for p in du_dashboard()["panels"]:
        danwei = (p.get("fieldConfig", {}).get("defaults", {}) or {}).get("unit")
        if not danwei:
            queshao.append(p.get("title"))
    assert queshao == [], "这些面板没设单位：%s" % queshao


def test_meige_mianban_dou_you_wushuju_tishi():
    """
    ★ 指导书要求"面板单位、Legend 和无数据状态清楚"。
    没数据时如果只显示空白，看的人分不清"是没数据"还是"服务挂了"。
    """
    queshao = []
    for p in du_dashboard()["panels"]:
        d = p.get("fieldConfig", {}).get("defaults", {}) or {}
        if "noValue" not in d:
            queshao.append(p.get("title"))
    assert queshao == [], "这些面板没设 noValue：%s" % queshao


def test_you_yuzhi_yanse_de_mianban():
    """至少要有带阈值着色的面板，否则看的人要自己脑补"什么算高"。"""
    you = sum(1 for p in du_dashboard()["panels"]
              if "thresholds" in (p.get("fieldConfig", {}).get("defaults", {}) or {}))
    assert you >= 5, "带阈值的面板只有 %d 个" % you


def test_fenweishu_mianban_cunzai():
    """必须有 p50/p95 延迟面板（实验要求"显示至少一个分位数"）。"""
    biao = " ".join(p.get("title", "") + " " + (p.get("description") or "")
                    for p in du_dashboard()["panels"])
    assert "p95" in biao
    assert "p50" in biao


def test_you_up_yu_ziyuan_mianban():
    biao = " ".join(p.get("title", "") for p in du_dashboard()["panels"])
    for guanjian in ("up", "CPU", "内存"):
        assert guanjian in biao, "缺少 %s 面板" % guanjian


def test_mianban_yinyong_de_shuju_yuan_uid_cunzai():
    """
    ★ 面板引用的 datasource uid 必须和 provisioning 里定义的一致。
    不一致的话导入后面板全是"No data"，而且报错信息很难懂。
    """
    with open(DS_LU, "r", encoding="utf-8") as f:
        ds = yaml.safe_load(f)
    uid_ji = {d["uid"] for d in ds["datasources"]}

    db = du_dashboard()
    yinyong = set()
    for p in db["panels"]:
        u = (p.get("datasource") or {}).get("uid")
        if u:
            yinyong.add(u)
        for t in p.get("targets", []):
            tu = (t.get("datasource") or {}).get("uid")
            if tu:
                yinyong.add(tu)
    assert yinyong, "面板没有引用任何数据源"
    assert yinyong <= uid_ji, "面板引用了不存在的数据源 uid：%s" % (yinyong - uid_ji)


def test_bianliang_dingyi_cunzai():
    """有模板变量说明是"可复用的面板"，不是一次性手画的。"""
    db = du_dashboard()
    ming = [v["name"] for v in db.get("templating", {}).get("list", [])]
    assert "job" in ming


def test_provisioning_zhi_xiang_zhengque_mulu():
    """
    ★ 配置文件要指向真实的 dashboards 目录。
    写死了别的路径，换台机器就导入不了。
    """
    with open(DB_LU, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    lujing = cfg["providers"][0]["options"]["path"]
    # 允许包含占位符（README 里说明要替换成项目实际路径）
    assert "dashboards" in lujing


def test_provisioning_buyunxu_jie_mian_gai():
    """
    allowUiUpdates 必须是 false。
    否则会出现"界面上改了、文件没变、换台机器就丢了"的经典问题。
    """
    with open(DB_LU, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert cfg["providers"][0]["allowUiUpdates"] is False


def test_yuzhi_he_gaojing_guize_yizhi():
    """
    ★ 面板上的阈值和告警规则的阈值要能对上。
    面板画红线 5%、告警却在 10% 触发，看的人会一脸问号。
    """
    with open(os.path.join(GEN, "prometheus", "alert-rules.yml"), "r",
              encoding="utf-8") as f:
        guize = yaml.safe_load(f)

    ga_yanchi = None
    for zu in guize["groups"]:
        for r in zu.get("rules", []):
            if "histogram_quantile" in r["expr"]:
                m = re.search(r"\)\s*>\s*([\d.]+)", r["expr"])
                if m:
                    ga_yanchi = float(m.group(1))

    db = du_dashboard()
    mian_yanchi = None
    for p in db["panels"]:
        if "p95" in (p.get("title") or ""):
            steps = p["fieldConfig"]["defaults"].get("thresholds", {}).get("steps", [])
            for s in steps:
                if s.get("value") is not None:
                    mian_yanchi = s["value"]
                    break

    assert ga_yanchi is not None, "找不到告警里的延迟阈值"
    # 面板上第一个黄色阈值应该和告警阈值同量级（不要求完全相等，
    # 面板可以更早变黄起到预警作用，但不能差一个数量级）
    assert mian_yanchi is not None
    assert abs(mian_yanchi - ga_yanchi) <= ga_yanchi, \
        "面板阈值 %s 和告警阈值 %s 差得太多" % (mian_yanchi, ga_yanchi)

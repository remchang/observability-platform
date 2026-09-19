# -*- coding: utf-8 -*-
"""
test_yichang.py —— 异常与恢复测试（实验要求 ≥3 条）。

★ 关于本组测试的边界（要讲清楚，不能含混）：
    真正"制造负载 / 延迟 / 停机"这件事需要 Prometheus 和 Grafana 在跑，
    而且要有人看着曲线。本机没有安装这两个组件，所以这一组测的是
    **异常注入接口本身是否安全可控**，以及**故障时应用不会崩**。

    "曲线是否按预期变化"这一条属于未实测部分，写在 docs/ceshi-jilu.md 里。
    这里不做任何"曲线符合预期"的断言——那是编数据。
"""
import os
import sys

import pytest

GEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUWU = os.path.join(GEN, "fuwu")
if FUWU not in sys.path:
    sys.path.insert(0, FUWU)

import fuzai  # noqa: E402


# ==================== 异常注入的安全边界 ====================

def test_fuzai_jujue_feihuiluo_mubiao():
    """
    ★ 负载脚本必须拒绝非本机目标。
    这不是形式主义——避免误把线上地址粘进来压测。
    """
    for huai in ("http://example.com", "http://192.168.1.10:8000",
                 "http://10.0.0.5", "https://www.baidu.com"):
        with pytest.raises(fuzai.FuzaiCuowu):
            fuzai.jiancha_mubiao(huai)


def test_fuzai_yunxu_huiluo_mubiao():
    for hao in ("http://127.0.0.1:8000", "http://localhost:8000"):
        assert fuzai.jiancha_mubiao(hao).startswith("http://")


def test_yanchi_canshu_yuejie_bei_jujue(kehu):
    """受控延迟必须限制在 0~2000ms，不能变成压测入口。"""
    assert kehu.get("/api/slow?delay_ms=3000").status_code == 400
    assert kehu.get("/api/slow?delay_ms=2001").status_code == 400
    assert kehu.get("/api/slow?delay_ms=2000").status_code == 200


def test_cuowu_canshu_yuejie_bei_jujue(kehu):
    assert kehu.get("/api/error?rate=1.5").status_code == 400
    assert kehu.get("/api/error?rate=-0.1").status_code == 400


# ==================== 三种负载模式 ====================

def test_fuzai_sanzhong_moshi_dou_you():
    assert set(fuzai.MOSHI.keys()) == {"wending", "yanchi", "cuowu"}


@pytest.mark.parametrize("moshi", ["wending", "yanchi", "cuowu"])
def test_moshi_chansheng_zhengque_shuliang(moshi):
    renwu = fuzai.MOSHI[moshi]("http://127.0.0.1:8000", 30)
    assert len(renwu) == 30
    assert all(u.startswith("http://127.0.0.1:8000") for u in renwu)


def test_yanchi_moshi_zhende_dai_yanchi_canshu():
    renwu = fuzai.MOSHI["yanchi"]("http://127.0.0.1:8000", 9)
    dai = [u for u in renwu if "delay_ms" in u]
    assert len(dai) == 3
    for u in dai:
        assert "delay_ms=" in u


def test_cuowu_moshi_yiban_shi_baocuo():
    renwu = fuzai.MOSHI["cuowu"]("http://127.0.0.1:8000", 10)
    baocuo = [u for u in renwu if "/api/error" in u]
    assert len(baocuo) == 5


# ==================== 故障下不崩 ====================

def test_fa_qingqiu_bu_hui_pao_yichang():
    """
    ★ 关键设计：发包函数**不抛异常**。
    负载测试要把失败也统计进去（状态码 0 表示网络层失败），
    如果抛异常整个测试就中断了，拿不到任何统计。
    """
    ma, haoshi, cuo = fuzai.fa_qingqiu("http://127.0.0.1:1/nothing", chaoshi=1)
    assert ma == 0
    assert cuo is not None
    assert haoshi >= 0


def test_500_bu_hui_dao_zhi_yingyong_bengkui(kehu):
    """连续触发 500，应用不能崩，之后正常请求仍然可用。"""
    for _ in range(5):
        assert kehu.get("/api/error?rate=1").status_code == 500
    assert kehu.get("/api/items").status_code == 200
    assert kehu.get("/healthz").status_code == 200


def test_healthz_ke_yong(kehu):
    """/healthz 必须和业务接口解耦：业务报错时它仍然可用。"""
    kehu.get("/api/error?rate=1")
    x = kehu.get("/healthz")
    assert x.status_code == 200
    assert x.json()["status"] == "ok"


def test_jianshang_shangpin_bucunzai_fanhui_500_dan_bubaolu(kehu):
    """
    边界输入（越界 ID）会抛 ValueError → 500。
    这里只断言"不崩 + 不泄露堆栈"，不假装它应该是 404
    （当前实现就是把越界当编程错误处理，这是有意的简化）。
    """
    x = kehu.get("/api/items/9999")
    assert x.status_code in (404, 500)
    assert "Traceback" not in x.text
    assert "ValueError" not in x.text

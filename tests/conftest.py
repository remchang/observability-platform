# -*- coding: utf-8 -*-
"""conftest.py —— 提供 FastAPI 测试客户端与指标快照工具。"""
import importlib
import os
import sys

GEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if GEN not in sys.path:
    sys.path.insert(0, GEN)

import pytest  # noqa: E402
from prometheus_client import REGISTRY  # noqa: E402


@pytest.fixture()
def kehu():
    """
    FastAPI 测试客户端。

    每个测试重新 reload app.main，让中间件和指标注册状态干净。
    注意 prometheus_client 的 REGISTRY 是**全局单例**，
    reload 不会重置它——所以测试里不能用"计数值刚好等于 N"这种断言，
    只能比较"调用前后的差值"。这一点在测试注释里也写了。
    """
    import app.main as main_module
    importlib.reload(main_module)
    # reload 不会重置 prometheus_client 的全局 REGISTRY，
    # 所以指标断言只能比较"调用前后的差值"，不能写死绝对值。
    from fastapi.testclient import TestClient
    # ★ raise_server_exceptions=False 是必须的：
    #   默认 True 时 TestClient 会把服务端异常**直接抛回测试**，
    #   我们就拿不到 500 响应，也测不了"异常请求有没有被计入 5xx"。
    with TestClient(main_module.app, raise_server_exceptions=False) as ke:
        yield ke


def qu_jishu(lu_you, fangfa, zhuangtai):
    """读某个标签组合的累计请求数。"""
    try:
        return REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": fangfa, "route": lu_you, "status": zhuangtai},
        ) or 0.0
    except Exception:            # noqa: BLE001
        return 0.0


def qu_yanchi_cishu(lu_you, fangfa):
    """读某个标签组合的延迟观测次数（Histogram 的 _count）。"""
    try:
        return REGISTRY.get_sample_value(
            "http_request_duration_seconds_count",
            {"method": fangfa, "route": lu_you},
        ) or 0.0
    except Exception:            # noqa: BLE001
        return 0.0


def qu_zhibiao_wenben(kehu):
    """/metrics 的原始文本。"""
    x = kehu.get("/metrics")
    assert x.status_code == 200
    return x.text


@pytest.fixture()
def jishu():
    """把两个查询函数打包成 fixture。"""
    return {"jishu": qu_jishu, "yanchi": qu_yanchi_cishu}

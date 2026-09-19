# -*- coding: utf-8 -*-
r"""
main.py —— 被监控的 Web 应用，暴露 /metrics。

跑法：
    .\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

（上面这个 docstring 用 r"" 是因为里面有反斜杠路径，
  不加 r 的话 Python 会报 SyntaxWarning: invalid escape sequence）

埋点的三条纪律：
  ① 用模板路由当标签，绝不用原始 URL 或用户 ID（高基数）
  ② 业务异常也要计 5xx，不能让异常绕过计数
  ③ /metrics 自己不计入流量指标，否则会自我污染
"""
import asyncio
import time
import random

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.zhibiao import (
    HTTP_QINGQIU_ZONGSHU,
    HTTP_YANCHI,
    YANCHI_ZHURU,
    YINGYONG_ZHUANGTAI,
    ZHENGZAI_CHULI,
    yanchi_fen_tong,
    yuchuli_lu_you,
    zhuce_windows_buchong,
)

app = FastAPI(title="被监控应用", version="1.0.0")

# 启动时注册 Windows 进程指标补充（非 Windows 自动跳过）
WIN_BOCHONG = zhuce_windows_buchong()

# 启动即视为正常
YINGYONG_ZHUANGTAI.set(1)

# 演示用的数据集。真实场景应该来自数据库。
SHANGPIN = [
    {"id": i, "mingcheng": "演示商品 %03d" % i, "jiage": 10.0 + i}
    for i in range(1, 21)
]


# ---------------- 埋点中间件 ----------------

@app.middleware("http")
async def zhibiao_zhongjianjian(request: Request, call_next):
    """
    记录请求数、延迟、在途数。

    ★ 为什么要 try/finally 而不是 try/except：
        异常也要计 5xx。如果只在正常路径计数，
        服务开始报错的时候指标反而"看不见错误"，
        这比没有监控还危险。
    """
    # /metrics 自己不计，不然抓一次就多一次请求数，自我污染
    if request.url.path == "/metrics":
        return await call_next(request)

    fangfa = request.method
    kaishi = time.perf_counter()

    ZHENGZAI_CHULI.inc()
    ma = 500
    try:
        xiangying = await call_next(request)
        ma = xiangying.status_code
        return xiangying
    except Exception:
        # 交给 FastAPI 的异常处理器变成 500，但计数必须在这里完成，
        # 否则异常请求根本不会被记进 http_requests_total
        ma = 500
        raise
    finally:
        ZHENGZAI_CHULI.dec()
        haoshi = time.perf_counter() - kaishi

        # ★ 踩过的坑：路由必须在 call_next **之后**取。
        #   中间件包在整个应用外面，在 call_next 之前 Starlette 还没做路由匹配，
        #   request.scope["route"] 是 None —— 于是所有请求都会被算成 unmatched，
        #   模板路由标签完全失效（一开始的测试就是全 0，查了半天才定位到这里）。
        lu_you = yuchuli_lu_you(request)

        # 用 finally：不管成功还是抛异常，一定会执行
        HTTP_QINGQIU_ZONGSHU.labels(
            method=fangfa, route=lu_you, status=str(ma)
        ).inc()
        HTTP_YANCHI.labels(method=fangfa, route=lu_you).observe(haoshi)


# ---------------- /metrics ----------------

@app.get("/metrics", include_in_schema=False)
def zhibiao_duqu():
    """
    暴露指标。用完整 Content-Type（带 charset 和 version 参数），
    有些采集端会校验这个头。
    """
    return Response(
        content=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )


# ---------------- 业务端点 ----------------

@app.get("/")
def shouye():
    return {
        "fuwu": "被监控应用",
        "shuoming": "指标在 /metrics，业务接口见 /docs",
        "windows_buchong": WIN_BOCHONG,
    }


@app.get("/healthz")
def jiankang():
    """
    应用级健康检查。

    它和 Prometheus 的 up 指标不是一回事：
      up 只说明"能抓到 /metrics"，说明不了业务依赖是否正常。
      这个接口可以加入数据库/下游检查，返回 503 表示应用自己认为不可用。
    """
    YINGYONG_ZHUANGTAI.set(1)
    return {"status": "ok"}


@app.get("/api/items")
def shangpin_liebiao():
    """正常端点：返回列表。用于产生稳定的请求量。"""
    return {"ok": True, "items": SHANGPIN}


@app.get("/api/items/{item_id}")
def shangpin_xiangqing(item_id: int):
    """
    ★ 这个端点是用来演示"模板路由做标签"的。
       访问 /api/items/1 和 /api/items/2 会产生**同一个** route 标签值
       （/api/items/{item_id}），所以标签基数只有 1。
       如果用了原始 URL，20 个商品就会产生 20 个时间序列。
    """
    if item_id < 1 or item_id > len(SHANGPIN):
        raise ValueError("商品不存在")
    return {"ok": True, "item": SHANGPIN[item_id - 1]}


@app.get("/api/slow")
async def shoushi_yanchi(delay_ms: int = 0):
    """
    受控延迟（异常实验用）。

    delay_ms 限制在 0~2000，防止误用成压测入口。
    真实系统里这种"测试专用参数"必须限制范围，并且最好只在非生产开启。
    """
    if delay_ms < 0 or delay_ms > 2000:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "xiaoxi": "delay_ms 必须在 0~2000 之间"},
        )
    if delay_ms > 0:
        YANCHI_ZHURU.labels(
            route="/api/slow", delay_ms_bucket=yanchi_fen_tong(delay_ms)
        ).inc()
        await asyncio.sleep(delay_ms / 1000.0)
    return {"ok": True, "delay_ms": delay_ms}


@app.get("/api/error")
def zhizao_cuowu(rate: float = 1.0):
    """
    受控错误（异常实验用）。

    rate 是"报错概率"，0~1。用来观察错误率面板的反应。
    """
    if rate < 0 or rate > 1:
        return JSONResponse(
            status_code=400, content={"ok": False, "xiaoxi": "rate 必须在 0~1 之间"}
        )
    if random.random() < rate:
        raise RuntimeError("这是受控制造的 500 错误，用于验证错误率指标")
    return {"ok": True, "rate": rate}


@app.get("/api/jitter")
def suiji_dou_dong():
    """
    随机抖动：故意让每次耗时不同。
    用来验证 Histogram 真的记录了分布，而不只是一个平均值。
    """
    return {"ok": True, "jitter_ms": round(random.uniform(1, 120), 1)}


# ---------------- 统一异常处理 ----------------

@app.exception_handler(Exception)
async def quanju_yichang(request: Request, e: Exception):
    """
    兜底：把未捕获异常变成 500。

    ★ 注意：**不要把异常消息原文返回给客户端**——
       那会泄露内部结构（文件路径、库版本、SQL 片段）。
       真正排障要去看日志，不是看响应体。
    """
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "xiaoxi": "服务器内部错误",
            "tishi": "详细原因见服务端日志，响应体不返回堆栈以防信息泄露",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

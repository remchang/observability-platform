# -*- coding: utf-8 -*-
"""
fuzai.py —— 本地受控负载脚本。

跑法：
    .\.venv\Scripts\python fuwu\fuzai.py --moshi hunhe --cishu 300 --bingfa 5

★ 安全约束（指导书明确要求）：
    只允许压测**本人自己的**服务。所以脚本里写死了目标必须是回环地址，
    传别的地址直接拒绝。这不是形式主义——避免误把线上地址粘进来。
"""
import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.error
import urllib.request

# 只允许本机。任何非回环地址直接拒绝。
YUNXU_ZHUJI = ("127.0.0.1", "localhost", "::1")


class FuzaiCuowu(Exception):
    pass


def jiancha_mubiao(jichu):
    """目标必须是回环地址。"""
    ti = jichu.lower()
    if not ti.startswith("http://"):
        raise FuzaiCuowu("只允许 http:// 的本地地址")
    zhuji = ti[len("http://"):].split("/")[0].split(":")[0]
    if zhuji not in YUNXU_ZHUJI:
        raise FuzaiCuowu(
            "只允许压测本机服务，%s 不在允许列表 %s 里。"
            "要压测别的地址请先确认有授权。" % (zhuji, list(YUNXU_ZHUJI))
        )
    return jichu.rstrip("/")


def fa_qingqiu(dizhi, chaoshi=10):
    """
    发一个请求，返回 (状态码, 耗时秒, 错误信息)。
    刻意不抛异常——负载测试要把失败也统计进去，不是中断整个测试。
    """
    kaishi = time.perf_counter()
    try:
        with urllib.request.urlopen(dizhi, timeout=chaoshi) as x:
            x.read()
            return x.status, time.perf_counter() - kaishi, None
    except urllib.error.HTTPError as e:
        # 4xx/5xx 也是有效结果（我们要观察错误率），不算脚本失败
        try:
            e.read()
        except Exception:      # noqa: BLE001
            pass
        return e.code, time.perf_counter() - kaishi, None
    except Exception as e:     # noqa: BLE001
        return 0, time.perf_counter() - kaishi, str(e)


# ---------------- 三种模式 ----------------

def moshi_wending(jichu, cishu):
    """稳定负载：反复打正常接口。用来看基线速率和延迟。"""
    lujing = ["/api/items", "/api/items/3", "/api/items/7", "/healthz", "/"]
    renwu = [jichu + lujing[i % len(lujing)] for i in range(cishu)]
    return renwu


def moshi_yanchi(jichu, cishu):
    """延迟实验：交替打正常接口和 /api/slow。用来看 p95 的变化。"""
    renwu = []
    for i in range(cishu):
        if i % 3 == 0:
            renwu.append("%s/api/slow?delay_ms=%d" % (jichu, 200 + (i % 4) * 150))
        else:
            renwu.append(jichu + "/api/items")
    return renwu


def moshi_cuowu(jichu, cishu):
    """错误实验：一半请求打 /api/error?rate=1。用来看错误率面板。"""
    renwu = []
    for i in range(cishu):
        if i % 2 == 0:
            renwu.append(jichu + "/api/error?rate=1")
        else:
            renwu.append(jichu + "/api/items")
    return renwu


MOSHI = {
    "wending": moshi_wending,
    "yanchi": moshi_yanchi,
    "cuowu": moshi_cuowu,
}


def pao(jichu, moshi, cishu, bingfa):
    jichu = jiancha_mubiao(jichu)
    renwu = MOSHI[moshi](jichu, cishu)

    print("目标：%s" % jichu)
    print("模式：%s   请求数：%d   并发：%d" % (moshi, cishu, bingfa))
    print("开始时间：%s" % time.strftime("%H:%M:%S"))
    print("-" * 56)

    kaishi = time.time()
    jieguo = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=bingfa) as chi:
        for r in chi.map(lambda u: (u, ) + fa_qingqiu(u), renwu):
            jieguo.append(r)

    zong = time.time() - kaishi
    haoshi = [j[2] for j in jieguo]
    zhuangtai = {}
    cuowu = []
    for _, ma, _, cuo in jieguo:
        zhuangtai[ma] = zhuangtai.get(ma, 0) + 1
        if cuo:
            cuowu.append(cuo)

    haoshi_paixu = sorted(haoshi)

    def fenwei(p):
        if not haoshi_paixu:
            return 0.0
        i = min(int(len(haoshi_paixu) * p), len(haoshi_paixu) - 1)
        return haoshi_paixu[i]

    baogao = {
        "mubiao": jichu,
        "moshi": moshi,
        "zong_qingqiu": len(renwu),
        "bingfa": bingfa,
        "zong_haoshi_s": round(zong, 3),
        "qps": round(len(renwu) / zong, 2),
        "zhuangtai_ma": {str(k): v for k, v in sorted(zhuangtai.items())},
        "cuowu_shu": len(cuowu),
        "yanchi": {
            "pingjun_ms": round(statistics.mean(haoshi) * 1000, 2) if haoshi else 0,
            "p50_ms": round(fenwei(0.50) * 1000, 2),
            "p95_ms": round(fenwei(0.95) * 1000, 2),
            "p99_ms": round(fenwei(0.99) * 1000, 2),
            "zuidai_ms": round(max(haoshi) * 1000, 2) if haoshi else 0,
        },
    }

    print(json.dumps(baogao, ensure_ascii=False, indent=2))
    print("-" * 56)
    print("★ 注意：这是**客户端看到的**延迟，不是服务端指标。")
    print("  两者可能不一致（网络、队列、客户端调度都会加时间）。")
    print("  报告里要写清用的是哪一个口径。")
    return baogao


def main():
    p = argparse.ArgumentParser(description="本地受控负载脚本")
    p.add_argument("--mubiao", default="http://127.0.0.1:8000",
                   help="只允许本机地址")
    p.add_argument("--moshi", choices=list(MOSHI.keys()), default="wending")
    p.add_argument("--cishu", type=int, default=200)
    p.add_argument("--bingfa", type=int, default=4)
    p.add_argument("--shuchu", default=None, help="把结果 JSON 写到这个文件")
    a = p.parse_args()

    try:
        baogao = pao(a.mubiao, a.moshi, a.cishu, a.bingfa)
    except FuzaiCuowu as e:
        print("拒绝执行：%s" % e)
        raise SystemExit(2)

    if a.shuchu:
        with open(a.shuchu, "w", encoding="utf-8") as f:
            json.dump(baogao, f, ensure_ascii=False, indent=2)
        print("结果已写入 %s" % a.shuchu)


if __name__ == "__main__":
    main()

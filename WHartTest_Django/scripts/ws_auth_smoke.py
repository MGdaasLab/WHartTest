"""平台侧 WebSocket 认证冒烟测试（对真实 uvicorn 实例执行）。

用法: python smoke.py <port> <strict:0|1> <actuator_secret>
"""
import asyncio
import json
import sys

import httpx
import websockets

BASE = "http://127.0.0.1:{port}"
WS = "ws://127.0.0.1:{port}"

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} | {name}" + (f" | {detail}" if detail else ""))


async def recv_welcome(ws, timeout=3):
    """读第一条消息（连接成功回执）；超时返回 None。"""
    try:
        return json.loads(await asyncio.wait_for(ws.recv(), timeout))
    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
        return None


async def expect_close(ws, expected_code):
    try:
        await asyncio.wait_for(ws.recv(), timeout=3)
        return False, "收到了消息而非关闭"
    except websockets.exceptions.ConnectionClosed as e:
        return e.rcvd is not None and e.rcvd.code == expected_code, f"close={e.rcvd.code if e.rcvd else None}"
    except asyncio.TimeoutError:
        return False, "3s 内未关闭"


async def get_token(port):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            BASE.format(port=port) + "/api/token/",
            json={"username": "smoketest", "password": "SmokePass123!"},
        )
        data = resp.json()
        return data["data"]["access"]


async def run_grace(port, secret):
    token = await get_token(port)

    # 1. 匿名 web 连接：兼容模式放行
    async with websockets.connect(WS.format(port=port) + "/ws/ui/web/") as ws:
        msg = await recv_welcome(ws)
        record("grace/匿名web连接放行", msg is not None and msg["code"] == 200)

    # 2. 伪造 token：拒绝 4401
    ws = await websockets.connect(WS.format(port=port) + "/ws/ui/web/?token=forged-token")
    ok, detail = await expect_close(ws, 4401)
    record("grace/伪造token拒绝(4401)", ok, detail)
    await ws.wait_closed()

    # 3. 有效 JWT：放行且识别为登录用户
    async with websockets.connect(WS.format(port=port) + f"/ws/ui/web/?token={token}") as ws:
        msg = await recv_welcome(ws)
        record("grace/有效JWT放行且识别用户", msg is not None and msg.get("user") == "smoketest",
               f"user={msg.get('user') if msg else None}")

    # 4. 执行器正确密钥：放行
    async with websockets.connect(WS.format(port=port) + f"/ws/ui/actuator/?id=act-A&token={secret}") as ws:
        msg = await recv_welcome(ws)
        record("grace/执行器正确密钥放行", msg is not None and msg.get("user") == "act-A")

    # 5. 执行器错误密钥：拒绝 4401
    ws = await websockets.connect(WS.format(port=port) + "/ws/ui/actuator/?id=act-B&token=wrong")
    ok, detail = await expect_close(ws, 4401)
    record("grace/执行器错误密钥拒绝(4401)", ok, detail)
    await ws.wait_closed()

    # 6/7. 抢注：act-A 在线时，第二个同 ID 连接被拒 4409，原连接不受影响
    ws_first = await websockets.connect(WS.format(port=port) + f"/ws/ui/actuator/?id=act-H&token={secret}")
    await recv_welcome(ws_first)
    ws_second = await websockets.connect(WS.format(port=port) + f"/ws/ui/actuator/?id=act-H&token={secret}")
    ok, detail = await expect_close(ws_second, 4409)
    record("grace/同ID抢注被拒(4409)", ok, detail)
    await ws_second.wait_closed()
    # 原连接仍可用（能收发）
    try:
        await ws_first.send(json.dumps({"code": 200, "msg": "ping", "is_notice": 0}))
        still_alive = True
    except websockets.exceptions.ConnectionClosed:
        still_alive = False
    record("grace/原执行器连接未被顶掉", still_alive)
    await ws_first.close()

    # 8. 伪造结果（grace：未登记来源放行，仅告警）——前端能收到广播
    async with websockets.connect(WS.format(port=port) + f"/ws/ui/web/?token={token}") as victim:
        await recv_welcome(victim)
        async with websockets.connect(WS.format(port=port) + f"/ws/ui/actuator/?id=act-F&token={secret}") as forge:
            await recv_welcome(forge)
            await forge.send(json.dumps({
                "code": 200, "msg": "result", "user": "smoketest", "is_notice": 1,
                "data": {"func_name": "u_case_result",
                         "func_args": {"case_id": 999, "status": "success", "message": "forged"}},
            }))
            try:
                got = json.loads(await asyncio.wait_for(victim.recv(), timeout=3))
                forwarded = got.get("data", {}).get("func_args", {}).get("message") == "forged"
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                forwarded = False
            record("grace/伪造结果被放行(预期行为:兼容模式不拦)", forwarded,
                   "兼容模式设计上放行，strict 模式拦截")


async def run_strict(port, secret):
    token = await get_token(port)

    # 1. 匿名 web：拒绝 4401
    ws = await websockets.connect(WS.format(port=port) + "/ws/ui/web/")
    ok, detail = await expect_close(ws, 4401)
    record("strict/匿名web拒绝(4401)", ok, detail)
    await ws.wait_closed()

    # 2. 匿名执行器：拒绝 4401
    ws = await websockets.connect(WS.format(port=port) + "/ws/ui/actuator/?id=act-anon")
    ok, detail = await expect_close(ws, 4401)
    record("strict/匿名执行器拒绝(4401)", ok, detail)
    await ws.wait_closed()

    # 3. 有效 JWT web：放行
    async with websockets.connect(WS.format(port=port) + f"/ws/ui/web/?token={token}") as ws:
        msg = await recv_welcome(ws)
        record("strict/有效JWT放行", msg is not None and msg.get("user") == "smoketest")

    # 4. 执行器正确密钥放行
    async with websockets.connect(WS.format(port=port) + f"/ws/ui/actuator/?id=act-S&token={secret}") as ws:
        msg = await recv_welcome(ws)
        record("strict/执行器正确密钥放行", msg is not None and msg.get("user") == "act-S")

    # 5. 伪造结果：执行器未登记任务来源，被拦截，受害者收不到
    async with websockets.connect(WS.format(port=port) + f"/ws/ui/web/?token={token}") as victim:
        await recv_welcome(victim)
        async with websockets.connect(WS.format(port=port) + f"/ws/ui/actuator/?id=act-F2&token={secret}") as forge:
            await recv_welcome(forge)
            await forge.send(json.dumps({
                "code": 200, "msg": "result", "user": "smoketest", "is_notice": 1,
                "data": {"func_name": "u_case_result",
                         "func_args": {"case_id": 999, "status": "success", "message": "forged"}},
            }))
            try:
                got = json.loads(await asyncio.wait_for(victim.recv(), timeout=3))
                # 唯一合法消息是连接回执；伪造广播不应出现
                forwarded = got.get("data", {}) and got["data"].get("func_args", {}).get("message") == "forged"
            except asyncio.TimeoutError:
                forwarded = False  # 预期：3s 内无任何广播
            except websockets.exceptions.ConnectionClosed:
                forwarded = False
            record("strict/伪造结果被拦截(受害者未收到)", not forwarded)


async def main():
    port, strict, secret = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    if strict == "0":
        await run_grace(port, secret)
    else:
        await run_strict(port, secret)
    failed = [r for r in results if not r[1]]
    print(f"\n{'=' * 50}\n总计: {len(results)}  通过: {len(results) - len(failed)}  失败: {len(failed)}")
    sys.exit(1 if failed else 0)


asyncio.run(main())

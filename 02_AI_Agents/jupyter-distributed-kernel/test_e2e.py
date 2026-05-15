"""
End-to-end test: connects as a client to the demo gateway,
creates a session, executes cells, and validates outputs.
"""
import asyncio
import json
import sys

import websockets

GATEWAY = "ws://localhost:8555/ws"


async def test():
    print("Connecting to gateway...")
    async with websockets.connect(GATEWAY) as ws:
        # 1. Create session
        await ws.send(json.dumps({
            "type": "session.create",
            "ts": 0, "id": "test1",
            "name": "E2E Test",
            "routing": "least_loaded",
        }))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert resp["type"] == "session.info", f"Expected session.info, got {resp['type']}"
        session_id = resp["session"]["session_id"]
        workers = resp.get("workers", [])
        print(f"✓ Session created: {session_id}")
        print(f"  Workers: {len(workers)}")
        for w in workers:
            print(f"    - {w['name']} ({w['capabilities']['platform']}, "
                  f"{w['capabilities']['cpu_count']} CPU, "
                  f"{w['capabilities']['memory_mb']}MB)")

        if not workers:
            print("✗ No workers connected — cannot run cells")
            return False

        # 2. Execute a simple cell
        print("\nExecuting: print('Hello distributed world!')")
        await ws.send(json.dumps({
            "type": "execute.request",
            "ts": 0, "id": "test2",
            "cell_id": "cell-001",
            "session_id": session_id,
            "code": "print('Hello distributed world!')",
        }))

        # Collect outputs until complete
        outputs = []
        complete = False
        while not complete:
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = json.loads(raw)
            if msg["type"] == "cell.output":
                outputs.append(msg)
                if msg.get("output_type") == "stream":
                    text = msg.get("data", {}).get("text", "")
                    print(f"  [stream] {text.rstrip()}")
                elif msg.get("output_type") == "status":
                    worker = msg.get("data", {}).get("worker", "?")
                    print(f"  [status] executing on {worker}")
            elif msg["type"] == "cell.complete":
                complete = True
                print(f"✓ Cell complete (status={msg.get('status', '?')})")
            elif msg["type"] == "cell.error":
                complete = True
                print(f"✗ Cell error: {msg.get('ename')}: {msg.get('evalue')}")
                return False
            elif msg["type"] == "worker.list":
                pass  # ignore worker list updates

        # Verify output
        stream_outputs = [m for m in outputs if m.get("output_type") == "stream"]
        assert any("Hello distributed world!" in m.get("data", {}).get("text", "")
                    for m in stream_outputs), "Expected output not found"
        print("✓ Output verified")

        # 3. Execute a cell with expression result
        print("\nExecuting: 2 + 2")
        await ws.send(json.dumps({
            "type": "execute.request",
            "ts": 0, "id": "test3",
            "cell_id": "cell-002",
            "session_id": session_id,
            "code": "2 + 2",
        }))

        outputs = []
        complete = False
        while not complete:
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = json.loads(raw)
            if msg["type"] == "cell.output":
                outputs.append(msg)
                ot = msg.get("output_type", "")
                if ot == "execute_result":
                    data = msg.get("data", {}).get("data", {})
                    print(f"  [result] {data.get('text/plain', '?')}")
                elif ot == "status":
                    pass
            elif msg["type"] == "cell.complete":
                complete = True
                print(f"✓ Cell complete")
            elif msg["type"] == "cell.error":
                complete = True
                print(f"✗ Cell error: {msg.get('ename')}: {msg.get('evalue')}")
                return False
            elif msg["type"] == "worker.list":
                pass

        result_msgs = [m for m in outputs if m.get("output_type") == "execute_result"]
        assert len(result_msgs) > 0, "Expected execute_result"
        assert "4" in result_msgs[0].get("data", {}).get("data", {}).get("text/plain", "")
        print("✓ Expression result verified: 4")

        # 4. Test stateful execution (namespace persists across cells)
        print("\nExecuting: x = 42")
        await ws.send(json.dumps({
            "type": "execute.request",
            "ts": 0, "id": "test4",
            "cell_id": "cell-003",
            "session_id": session_id,
            "code": "x = 42",
        }))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = json.loads(raw)
            if msg["type"] in ("cell.complete", "cell.error"):
                break

        print("Executing: x * 2")
        await ws.send(json.dumps({
            "type": "execute.request",
            "ts": 0, "id": "test5",
            "cell_id": "cell-004",
            "session_id": session_id,
            "code": "x * 2",
        }))
        outputs = []
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = json.loads(raw)
            if msg["type"] == "cell.output":
                outputs.append(msg)
            elif msg["type"] in ("cell.complete", "cell.error"):
                break

        result_msgs = [m for m in outputs if m.get("output_type") == "execute_result"]
        assert len(result_msgs) > 0
        assert "84" in result_msgs[0].get("data", {}).get("data", {}).get("text/plain", "")
        print("✓ Stateful execution verified: x*2 = 84")

        # 5. Test error handling
        print("\nExecuting: 1/0")
        await ws.send(json.dumps({
            "type": "execute.request",
            "ts": 0, "id": "test6",
            "cell_id": "cell-005",
            "session_id": session_id,
            "code": "1/0",
        }))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = json.loads(raw)
            if msg["type"] == "cell.error":
                assert msg.get("ename") == "ZeroDivisionError"
                print(f"✓ Error handled: {msg['ename']}: {msg['evalue']}")
                break
            elif msg["type"] == "cell.complete":
                break

        print("\n═══ ALL TESTS PASSED ═══")
        return True


if __name__ == "__main__":
    ok = asyncio.run(test())
    sys.exit(0 if ok else 1)

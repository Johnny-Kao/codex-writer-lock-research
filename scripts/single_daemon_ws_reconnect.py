#!/usr/bin/env python3
"""Isolated single-daemon, two-WebSocket-connection handoff test.

The daemon stays running when A's socket closes without unsubscribe.
No real CODEX_HOME, credentials, external network, or user thread is accessed.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import uuid

import websockets

async def rpc(ws, method, params, rid):
    await ws.send(json.dumps({"jsonrpc":"2.0","id":rid,"method":method,"params":params}))
    for _ in range(50):
        message=json.loads(await asyncio.wait_for(ws.recv(), timeout=12))
        if message.get("id")==rid:
            return message
    raise AssertionError("response not received")

async def initialize(ws):
    r=await rpc(ws,"initialize",{"clientInfo":{"name":"writer-lock-single-daemon-test","version":"0.1"},"capabilities":{}},1)
    assert "result" in r, r
    await ws.send(json.dumps({"jsonrpc":"2.0","method":"initialized","params":{}}))

async def main(codex, delay):
    with tempfile.TemporaryDirectory(prefix="codex-ws-handoff-") as home:
        workspace=Path(home)/"workspace"
        workspace.mkdir()
        thread_id=str(uuid.uuid4())
        folder=Path(home)/"sessions"/"2025"/"01"/"05"
        folder.mkdir(parents=True)
        meta={"timestamp":"2025-01-05T12:00:00Z","type":"session_meta",
              "payload":{"session_id":thread_id,"id":thread_id,"timestamp":"2025-01-05T12:00:00Z",
                         "cwd":str(workspace),"originator":"codex","cli_version":"0.0.0",
                         "source":"cli","model_provider":"openai"}}
        event={"timestamp":"2025-01-05T12:00:00Z","type":"event_msg",
               "payload":{"type":"user_message","message":"Synthetic connection handoff","kind":"plain"}}
        (folder/f"rollout-2025-01-05T12-00-00-{thread_id}.jsonl").write_text(
            json.dumps(meta)+"\n"+json.dumps(event)+"\n")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0))
            port=sock.getsockname()[1]
        env=dict(os.environ,CODEX_HOME=home)
        env.pop("CODEX_REMOTE_AUTH_TOKEN",None)
        process=subprocess.Popen([codex,"-c",f"thread_unload_delay_secs={delay}",
                                  "app-server","--listen",f"ws://127.0.0.1:{port}"],
                                  env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        url=f"ws://127.0.0.1:{port}"
        try:
            for _ in range(100):
                try:
                    a=await websockets.connect(url)
                    break
                except OSError:
                    await asyncio.sleep(0.1)
            else:
                raise AssertionError("app-server did not start")
            try:
                await initialize(a)
                first=await rpc(a,"thread/resume",{"threadId":thread_id},2)
                assert "result" in first, first
                print("A resumed persisted synthetic thread")
                async with websockets.connect(url) as b:
                    await initialize(b)
                    concurrent=await rpc(b,"thread/resume",{"threadId":thread_id},2)
                    print("B same-daemon resume while A connected:",
                          "success" if "result" in concurrent else concurrent.get("error"))
                    # Simulate loss of mobile connection without an unsubscribe, while server lives.
                    await a.close()
                    assert process.poll() is None, "daemon stopped during client disconnect"
                    await asyncio.sleep(1)
                    resumed=await rpc(b,"thread/resume",{"threadId":thread_id},3)
                    print("B resume after A socket disconnect:",
                          "success" if "result" in resumed else resumed.get("error"))
                    assert "result" in resumed, resumed
                    assert process.poll() is None, "daemon stopped after reconnect"
                    print("PASS: same daemon stayed alive; reconnect succeeded")
            finally:
                await a.close()
        finally:
            process.terminate()
            try: process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--codex",default=shutil.which("codex"))
    ap.add_argument("--unload-delay",type=int,default=1800)
    args=ap.parse_args()
    if not args.codex: ap.error("codex binary missing")
    asyncio.run(main(args.codex,args.unload_delay))

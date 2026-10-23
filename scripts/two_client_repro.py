#!/usr/bin/env python3
"""Isolated two-process Codex writer ownership test; never targets live daemon.

Tests thread/start -> competing thread/resume -> unsubscribe -> retry.
No model turns, credentials, existing sessions, or project files required.
"""
import argparse
import json
import os
import pathlib
import select
import shutil
import subprocess
import tempfile
import time

class Client:
    def __init__(self, codex, env, unload_delay):
        self.p = subprocess.Popen([codex, "-c", f"thread_unload_delay_secs={unload_delay}",
                                   "app-server"], env=env, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  bufsize=0, start_new_session=True)
        self.next_id = 0
        self.buffer = b""

    def rpc(self, method, params=None, timeout=12):
        self.next_id += 1
        rid = self.next_id
        data = {"jsonrpc": "2.0", "id": rid, "method": method,
                "params": {} if params is None else params}
        self.p.stdin.write((json.dumps(data) + "\n").encode())
        self.p.stdin.flush()
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if b"\n" in self.buffer:
                raw, self.buffer = self.buffer.split(b"\n", 1)
                try:
                    obj = json.loads(raw)
                except ValueError:
                    continue
                if obj.get("id") == rid:
                    return obj
                continue
            waiting = until - time.monotonic()
            if waiting <= 0:
                break
            ready, _, _ = select.select([self.p.stdout], [], [], waiting)
            if not ready:
                break
            part = os.read(self.p.stdout.fileno(), 65536)
            if not part:
                break
            self.buffer += part
        return {"timeout": method}

    def close(self):
        if self.p.poll() is None:
            self.p.terminate()
            try:
                self.p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codex", default=shutil.which("codex"))
    ap.add_argument("--unload-delay", type=int, default=0)
    args = ap.parse_args()
    if not args.codex:
        ap.error("codex unavailable")
    with tempfile.TemporaryDirectory(prefix="codex-writer-research-") as home:
        env = dict(os.environ, CODEX_HOME=home)
        env.pop("CODEX_REMOTE_AUTH_TOKEN", None)
        cwd = str(pathlib.Path(home) / "workspace")
        pathlib.Path(cwd).mkdir()
        a = Client(args.codex, env, args.unload_delay)
        b = Client(args.codex, env, args.unload_delay)
        try:
            for c in (a, b):
                response = c.rpc("initialize", {
                    "clientInfo": {"name": "writer-lock-research", "version": "0.1"},
                    "capabilities": {}})
                print("initialize:", "ok" if "result" in response else response)
                c.p.stdin.write((json.dumps({"jsonrpc": "2.0",
                                             "method": "initialized",
                                             "params": {}}) + "\n").encode())
                c.p.stdin.flush()
            start = a.rpc("thread/start", {"cwd": cwd})
            thread_id = start.get("result", {}).get("thread", {}).get("id")
            print("thread/start:", "ok" if thread_id else start)
            if not thread_id:
                return
            print("B concurrent resume:", b.rpc("thread/resume", {"threadId": thread_id}))
            unsub = a.rpc("thread/unsubscribe", {"threadId": thread_id})
            print("A unsubscribe:", unsub)
            time.sleep(2)
            print("B resume after unsubscribe:", b.rpc("thread/resume", {"threadId": thread_id}))
            print("isolated lock files:", len(list((pathlib.Path(home) / "thread-writer-locks").glob("*.lock"))))
        finally:
            b.close()
            a.close()
    print("disposed isolated CODEX_HOME; existing daemon unaffected")

if __name__ == "__main__":
    main()

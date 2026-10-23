#!/usr/bin/env python3
"""Safe, dependency-free smoke test of isolated Codex app-server startup.

Creates a disposable CODEX_HOME and starts a standalone stdio app-server.
Never reads ~/.codex or targets a managed daemon. This is a transport probe,
NOT a reproduction of the remote-control writer-lock bug.
"""
import argparse
import os
import pathlib
import select
import shutil
import subprocess
import tempfile
import time
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex", default=shutil.which("codex"))
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()
    if not args.codex:
        parser.error("codex binary not found; pass --codex /path/to/codex")
    with tempfile.TemporaryDirectory(prefix="codex-writer-research-") as root:
        env = dict(os.environ)
        env["CODEX_HOME"] = root
        env.pop("CODEX_REMOTE_AUTH_TOKEN", None)
        proc = subprocess.Popen(
            [args.codex, "app-server"],
            env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0, start_new_session=True,
        )
        request = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": "writer-lock-research", "version": "0.1"},
                       "capabilities": {}},
        }
        try:
            proc.stdin.write((json.dumps(request) + "\n").encode())
            proc.stdin.flush()
            ready, _, _ = select.select([proc.stdout], [], [], args.timeout)
            if ready:
                raw = os.read(proc.stdout.fileno(), 65536).decode("utf-8", "replace")
                print("initialize response:", raw[:1500])
            else:
                print("No initialize response within timeout (inconclusive).")
            paths = sorted(str(p.relative_to(root)) for p in pathlib.Path(root).rglob("*") if p.is_file())
            print("isolated CODEX_HOME files:", paths[:25])
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    print("Disposable environment removed; no existing threads touched.")

if __name__ == "__main__":
    main()

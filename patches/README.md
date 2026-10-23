# Experimental fix: explicit unsubscribe handoff

This **uncompiled experimental patch** targets openai/codex HEAD `f3a90545aed3188ee1e5c119ec89a742de399cdc` and should not be deployed to a live daemon.

## Intent

Keep the existing 1800-second grace period for abrupt disconnects (to support reconnect). On an **explicit** `thread/unsubscribe` that removes the last subscriber, publish a one-way handoff request. `UnloadingState` can then initiate existing guarded unload logic without waiting for the grace period, provided the thread has no active turn. A fresh subscriber resets the handoff request. The existing pending-unload and agent-running checks remain unchanged.

## Validation

```
cd /path/to/openai-codex
 git apply --check /path/to/explicit-unsubscribe-handoff.patch
 git apply /path/to/explicit-unsubscribe-handoff.patch
 cargo test -p codex-app-server
 python3 /path/to/two_client_repro.py --codex /path/to/patched/codex --unload-delay 1800 --expect-handoff
```

The unmodified Codex 0.160.0/0.163.0 **fails** `--expect-handoff` at a 1800-second delay; with zero delay it passes. No build or Rust test run has yet been completed for this patch because the connected M5 does not have `cargo`/`rustfmt` on PATH.

## Limits

- This patch addresses **explicit unsubscribe only**. It does not establish that iOS always sends unsubscribe. Unclean client disconnect behavior and active-turn semantics require additional regression tests.
- A separate Rust regression test and formatter/build validation are required before describing the patch as ready for upstream.
- Never delete an active `.lock` file or bypass the writer guard.

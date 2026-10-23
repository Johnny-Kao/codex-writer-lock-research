# Codex app-server writer-lock research

Public, independent investigation of Codex thread ownership, idle unload, and Remote Control client handoff.

**Status: research setup. No fix or upstream closure is claimed.**

## Why

In [openai/codex#44449](https://github.com/openai/codex/issues/44449), multiple users describe a session held by a managed app-server even after the controlling UI or CLI disconnects. Subsequent clients get `thread <id> already has an active writer`. Related discussions: [#37403](https://github.com/openai/codex/issues/37403), [#40167](https://github.com/openai/codex/issues/40167).

### Hypotheses (unconfirmed)

1. Disconnect and explicit `thread/unsubscribe` do not always result in equivalent subscriber cleanup.
2. An unloaded/idle thread can retain the recorder's single-writer guard longer than intended.
3. Reconnect can attempt a second resume instead of attaching to a thread already loaded within the same daemon.
4. The default idle unload delay (30 minutes) may contribute to perceived ownership retention; it is not by itself evidence of a bug.

## Boundaries

- **Never attach to or kill an existing user's daemon.**
- Do not inspect or publish existing `~/.codex/sessions`, auth state, or local project files.
- All experiments use a temporary **CODEX_HOME** and disposable threads only.
- Do not manually unlink a live writer-lock file.
- Do not weaken single-writer safety just to suppress a UI error.
- No paid CI runners.

## Research sequence

1. Establish an isolated app-server JSON-RPC connection and create a disposable thread.
2. Record the status of its recorder and `thread-writer-locks`.
3. Compare `thread/unsubscribe`, normal client exit, abrupt disconnect, and reconnect.
4. Compare `thread_unload_delay_secs=0` against the default only after verifying no active turns.
5. Test two clients/servers and ensure **only one writer** can append at a time.
6. Implement a minimal Rust fix only after a failing upstream regression test is obtained.

See [TEST_PLAN.md](TEST_PLAN.md) and [scripts/isolated_probe.py](scripts/isolated_probe.py).

## Upstream code to inspect

- [app-server thread state](https://github.com/openai/codex/blob/main/codex-rs/app-server/src/thread_state.rs)
- [thread lifecycle](https://github.com/openai/codex/blob/main/codex-rs/app-server/src/request_processors/thread_lifecycle.rs)
- [thread processor](https://github.com/openai/codex/blob/main/codex-rs/app-server/src/request_processors/thread_processor.rs)

This repository is not affiliated with or endorsed by OpenAI.

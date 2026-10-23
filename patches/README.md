# Experimental patch — explicit unsubscribe writer handoff

**Status (23 October 2026): compiled and tested in isolated GitHub-hosted Linux CI; not an upstream-merged or production-deployed fix.**

This Rust patch targets [openai/codex](https://github.com/openai/codex), pinned to upstream commit `f3a90545aed3188ee1e5c119ec89a742de399cdc`.

## Problem and intended effect

With the default `thread_unload_delay_secs=1800` (30 minutes), an app-server can continue to hold exclusive writer ownership after its last client **explicitly unsubscribes** from an idle thread. A separate app-server attempting to resume the same persisted thread then receives `already has an active writer`. The zero-delay baseline succeeds; the 1,800-second unmodified baseline does not after a two-second retry.

This patch records explicit relinquishment from the last subscriber and permits the existing guarded idle unload to run without waiting for the ordinary grace period. It preserves normal grace behavior for unexpected disconnects, as well as safeguards around active turns. It does **not** disable writer exclusivity.

## Changed upstream files

- `codex-rs/app-server/src/thread_state.rs` — explicit handoff watcher, set on final unsubscribe and reset on subscribe.
- `codex-rs/app-server/src/request_processors/thread_lifecycle.rs` — guarded zero-delay unload on explicit handoff.

Patch file: [explicit-unsubscribe-handoff.patch](explicit-unsubscribe-handoff.patch).

## Verified results

[GitHub Actions Run #18 — SUCCESS](https://github.com/Johnny-Kao/codex-writer-lock-research/actions/runs/39911708910):

- Patch applies and patched CLI compiles.
- **398 / 398** app-server library unit tests passed; no skipped unit tests.
- Concurrent second writer blocked while A owns the session.
- Two-server explicit-unsubscribe handoff passes with delay = 1,800 seconds and with delay = 0.
- Process-exit without unsubscribe: competing app-server resumes.
- Single live daemon / two WebSocket clients: after A disconnects without unsubscribe, B resumes in isolated simulation.

**Scope caveat:** the last two tests cover distinct scenarios. The single-daemon WebSocket case has no unpatched control, so its success does not establish that the explicit-unsubscribe patch fixed unexpected client disconnect. Actual iPhone Remote Control routing, active-turn disconnection, and production operation remain unverified.

## Reproduce

Use the commands in [the pinned CI workflow](../.github/workflows/codex-writer-regression.yml) to clone the correct upstream SHA, apply the patch, compile and execute all cases. The harness creates temporary synthetic `CODEX_HOME` data; never aim it at an existing managed daemon.

The report and research PR are independent work in this repository, **not an upstream submission or acceptance**. See [the main report](../README.md) and [Draft PR #2](https://github.com/Johnny-Kao/codex-writer-lock-research/pull/2).

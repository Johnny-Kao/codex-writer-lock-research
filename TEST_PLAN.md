# Test plan and evidence — 23 October 2026

This file complements the [main research report](README.md). It distinguishes **behavior shown in isolated tests** from the still-unverified production Remote Control incident.

## Regression matrix

| ID | Scenario | CI evidence | Status |
| --- | --- | --- | --- |
| T01 | Compile patched Codex at pinned upstream commit | Run #18 | PASS |
| T02 | All app-server library unit tests | 398 passed, 0 failed | PASS |
| T03 | Two app-server processes; B attempts concurrent resume while A owns thread | B rejected with active writer | PASS |
| T04 | A explicitly unsubscribes with default 1,800-second grace; B retries | B resumes on patched build | PASS |
| T05 | Same test with zero-second grace | B resumes | PASS |
| T06 | A's app-server process exits without unsubscribe; B retries | B resumes | PASS |
| T07 | A closes WebSocket without unsubscribe; same daemon stays up; B resumes | B resumes in isolated simulation | PASS |
| T08 | Actual iOS/Remote Control bridge and mobile background behavior | No end-to-end run | NOT TESTED |
| T09 | Drop connection during an active model turn; ensure turn and ownership remain safe | No end-to-end run | NOT TESTED |
| T10 | Compare patched vs unmodified source for same-daemon WebSocket reconnection | No unpatched control | NOT TESTED |

**Verified run:** [GitHub Actions #18](https://github.com/Johnny-Kao/codex-writer-lock-research/actions/runs/39911708910).

## Baseline evidence

Tested with isolated Codex CLI 0.160.0 and 0.163.0 and synthetic persisted JSONL rollout in a disposable `CODEX_HOME`. Neither test used an existing account or model turn.

| Event | Unmodified delay = 0 s | Unmodified delay = 1,800 s |
| --- | --- | --- |
| A resumes thread | PASS | PASS |
| B tries concurrently | Rejected: active writer | Rejected: active writer |
| A calls `thread/unsubscribe` | Unsubscribed | Unsubscribed |
| B retries about two seconds later | PASS | FAIL: active writer |

This demonstrates grace-period writer retention, **not by itself a security bug or unintended subscriber leak**.

## Patch validation

On pinned upstream commit `f3a90545aed3188ee1e5c119ec89a742de399cdc`, the patch adds a signal for the *last explicit unsubscribe*. It may accelerate unload **only when existing active-turn checks allow it**. It does not disable the writer guard.

The main observed improvement is successful cross-process handoff in the 1,800-second setting. The unexpected process exit and same-daemon WebSocket cases are valuable behavior checks, but neither proves patch causality.

## How to reproduce

See [workflow](.github/workflows/codex-writer-regression.yml), [two-process harness](scripts/two_client_repro.py), and [same-daemon WebSocket harness](scripts/single_daemon_ws_reconnect.py). These run on an isolated GitHub-hosted Linux runner, with synthetic sessions and an ephemeral `CODEX_HOME`.

A filename in `thread-writer-locks` is not by itself proof of a held OS lock. Use an actual competing `thread/resume` operation to test ownership.

## Unresolved questions

1. Does real Remote Control transport emit `thread/unsubscribe` on mobile backgrounding or disconnect?
2. Under which paths do two UI connections share one daemon versus create competing app-servers?
3. What happens when a client disconnects in the middle of an active turn?
4. Does the same-daemon WebSocket path behave identically on **unmodified** upstream source?

No production deployment or upstream acceptance is claimed.

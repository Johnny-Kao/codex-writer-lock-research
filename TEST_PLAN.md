# Test matrix and acceptance criteria

| ID | Lifecycle | Expected behavior |
|---|---|---|
| T01 | Initialize client; create disposable thread | Thread ID returned and persisted only in isolated CODEX_HOME |
| T02 | Client A unsubscribes after idle turn | No stale subscriber; thread eventually unloads according to policy |
| T03 | Client A exits normally | Same idle cleanup policy as unsubscribe, with no active turn interrupted |
| T04 | Client A disconnects abruptly | Reaper eventually removes the subscriber; no permanent writer |
| T05 | Client B resumes after A disconnects | Resume succeeds after valid handoff/unload |
| T06 | A still executes an active turn; B attempts resume | No dual-writer and no data corruption |
| T07 | Compare idle delay 0 vs default 1800 s | Distinguish policy retention from missing unsubscribe |
| T08 | Repeated B reconnect/resume | No leaked subscriber references; stable writer state |

A correct fix needs: (a) a failing regression test before patch, (b) passing test with patch, (c) no parallel appenders, (d) safe active-turn behavior, and (e) cross-process verification.

## Current evidence level

- Real-user issue and local PID/lock observations exist, but **no sanitized public reproduction or patch has yet passed**.
- Public research must use synthetic thread IDs and temporary paths.
- Do not paste the user’s actual session identifiers, payloads, secrets, hostname, or account information here.

## Important distinction

A writer lock held during a documented unload grace period is not automatically incorrect. Determine whether the owning app-server has subscribers, active turns, pending I/O, or a scheduled unload before attributing a lifecycle defect.


## 2026-10-23: isolated two-server result (Codex CLI 0.160.0, macOS)

Synthetic persisted JSONL fixture, isolated `CODEX_HOME`, two standalone stdio app-servers, **no actual model turn**:

| Event | unload delay 0 | unload delay 1800 |
|---|---|---|
| Server A `thread/resume` | PASS | PASS |
| Server B `thread/resume` while A owns thread | `-32600 already has an active writer` | same |
| Server A `thread/unsubscribe` | `unsubscribed` | `unsubscribed` |
| 2 seconds later Server B `thread/resume` | **PASS** | **-32600 active writer** |

This supports the hypothesis that **configured idle unload grace time can retain writer ownership after unsubscribing**, even when no model turn is in progress. It does NOT prove an erroneous subscriber leak or Remote Control backend fault. A temporary lock **filename count is not an ownership measurement**; lock release was verified operationally by successful competing resume in the zero-delay case.

Reproduce:
```sh
python3 scripts/two_client_repro.py --unload-delay 0
python3 scripts/two_client_repro.py --unload-delay 1800
```

Next: test unexpected socket disconnect, retained subscription, active-turn protection, and CLI 0.163.x. Do not change a real daemon's configuration without assessing effects on remote reattachment.

## Confirmation on Codex managed-daemon binary 0.163.0

Repeated both A/B cases using the **standalone executable** from the installed 0.163.0 package, without connecting to the running managed daemon. Results match 0.160.0 exactly: delay=0 allows resume after unsubscribe; delay=1800 retains exclusive writer ownership after unsubscribe. This reproduces the grace-period behavior in the same version family as the reported issue, but does not independently prove a buggy disconnect handler.

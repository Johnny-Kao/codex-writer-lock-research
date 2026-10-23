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

# Codex Writer Ownership & Client Handoff
## Reproduction and Patch Validation Report

**Investigated:** 23 October 2026 · **Upstream:** [openai/codex](https://github.com/openai/codex) · **Status:** isolated reproduction and patch validation complete; production Remote Control resolution **not established**.

This repository documents an independent investigation into Codex app-server thread ownership when control moves between clients or server processes. It contains a reproducible test harness, a small experimental Rust patch, and CI evidence. It is **not an upstream Codex fix or an official OpenAI report**.

### At a glance

| Question | Finding |
| --- | --- |
| What failed? | A subsequent app-server attempting to resume a persisted thread received `-32600: thread … already has an active writer`, even after the previous client explicitly unsubscribed. |
| When does it reproduce? | With a synthetic, persisted, idle thread and the default **1,800-second** unload grace period. A zero-second control can resume. |
| What did we change? | Treat the **last explicit `thread/unsubscribe`** as an early-handoff signal, subject to existing idle / active-turn safety checks. |
| What improved? | In the isolated two-server regression, the waiting server resumes after explicit unsubscribe **without having to wait through the 30-minute grace period**. |
| Was exclusivity preserved? | Yes in the tested scenario: a second server is rejected while the first remains the writer. |
| Did CI pass? | **Yes:** [GitHub Actions Run #18](https://github.com/Johnny-Kao/codex-writer-lock-research/actions/runs/39911708910), including **398/398** app-server unit tests and integration checks. |
| Is the reported iPhone Remote Control issue fixed? | **Not demonstrated.** A simulated same-daemon WebSocket reconnect passed, but does not prove that the patch caused that outcome or that the actual mobile Remote Control path behaves identically. |

### 1. Incident and motivation

The investigation started **23 October 2026** after a Codex Remote Control handoff from a mobile client produced an error of the form:

```text
Another Codex session is using this task
thread <id> already has an active writer
```

The originating app-server could remain running in the background. This matters because a user may legitimately switch between interfaces without intending to create two simultaneous writers. The challenge is to allow **safe ownership transfer** without weakening Codex's single-writer protection.

Related upstream discussion: [openai/codex#44449](https://github.com/openai/codex/issues/44449); additional contextual issues: [#37403](https://github.com/openai/codex/issues/37403) and [#40167](https://github.com/openai/codex/issues/40167). This repository is an *independent investigation*; it does not assert that these issues share an identical root cause.

### 2. Reproduction: separating policy from a defect

Two isolated app-server processes share a disposable `CODEX_HOME` containing a **synthetic persisted rollout** (no personal session, credentials, or live project). The first server resumes the thread; the second attempts to resume the same thread.

| Sequence | Grace = 0 s | Grace = 1,800 s |
| --- | --- | --- |
| A resumes the persisted idle thread | Successful | Successful |
| B attempts a concurrent resume | Rejected: active writer | Rejected: active writer |
| A explicitly calls `thread/unsubscribe` | Unsubscribed | Unsubscribed |
| B retries ~2 seconds later against unmodified Codex | **Successful** | **Rejected: active writer** |
| B retries after applying the experimental patch | **Successful** | **Successful** |

The baseline behavior was reproduced with standalone Codex **0.160.0 and 0.163.0** in an isolated local experiment; the patched 1,800-second scenario was subsequently verified on GitHub-hosted Linux CI against upstream commit `f3a90545aed3188ee1e5c119ec89a742de399cdc`.

**Interpretation:** retaining ownership during a configured grace period may be intentional. The specific improvement investigated here is the distinction between a client that **explicitly relinquishes** a thread and one that disconnects unintentionally and may reconnect. A lock file existing on disk is **not** evidence that its OS-level lock is still held; the competing `thread/resume` result is the operational check.

### 3. Proposed change

The experimental patch modifies two upstream Rust files:

- [`codex-rs/app-server/src/thread_state.rs`](https://github.com/openai/codex/blob/f3a90545aed3188ee1e5c119ec89a742de399cdc/codex-rs/app-server/src/thread_state.rs): track an explicit-handoff signal when the last subscriber unsubscribes; clear it when a subscriber attaches.
- [`codex-rs/app-server/src/request_processors/thread_lifecycle.rs`](https://github.com/openai/codex/blob/f3a90545aed3188ee1e5c119ec89a742de399cdc/codex-rs/app-server/src/request_processors/thread_lifecycle.rs): use the existing guarded idle-unload path with **zero wait** for that explicit handoff, instead of applying the normal grace interval.

The patch retains normal disconnect grace and existing active-turn checks. It does **not** remove writer locks, allow simultaneous writers, force-kill a daemon, or change the default delay globally.

Patch: [`patches/explicit-unsubscribe-handoff.patch`](patches/explicit-unsubscribe-handoff.patch) · [Experimental Draft PR #2](https://github.com/Johnny-Kao/codex-writer-lock-research/pull/2) (in this research repo, **not** an upstream PR).

### 4. Validation and evidence

All below executed with temporary, synthetic session data. The CI runs on a **GitHub-hosted Ubuntu runner**, not on any production Mac.

| Test | Evidence / result |
| --- | --- |
| Patch applies; patched CLI compiles | **PASS** |
| App-server Rust unit tests | **398 passed, 0 failed** |
| Contending second writer rejected before relinquishment | **PASS** |
| Explicit unsubscribe with 1,800-second grace → competing resume | **PASS** |
| Zero-delay handoff control | **PASS** |
| First server process terminated without unsubscribe → other server resumes | **PASS** |
| **One live daemon**, two WebSocket clients; A closes its socket without unsubscribe, B resumes | **PASS** in the isolated simulation |
| Real iPhone Remote Control connection/recovery | **Not tested** |
| Background task still executing during a network drop | **Not tested** |
| Proof that same-daemon WebSocket success requires this Rust patch | **Not established** |

**Final successful CI:** [Run #18](https://github.com/Johnny-Kao/codex-writer-lock-research/actions/runs/39911708910). Early runs helped identify CI-only prerequisites: expanded Rust test-thread stack and build of the `test_stdio_server` fixture. The full suite passed without skipping unit tests.

**Important attribution limit:** the same-daemon WebSocket test verifies *reconnection behavior* on the patched build; it does not isolate patch efficacy, because the change intentionally targets the explicit-unsubscribe path. That test needs an unpatched control before making a causal claim.

### 5. Reproduction tools

- [`scripts/two_client_repro.py`](scripts/two_client_repro.py) — isolated two-process writer competition, explicit unsubscribe, and abrupt server termination.
- [`scripts/single_daemon_ws_reconnect.py`](scripts/single_daemon_ws_reconnect.py) — isolated live daemon with two WebSocket connections; simulates a client socket closing without unsubscribe while the daemon stays alive.
- [`.github/workflows/codex-writer-regression.yml`](.github/workflows/codex-writer-regression.yml) — pins upstream source, applies patch, compiles, runs unit tests and both harnesses.
- [`TEST_PLAN.md`](TEST_PLAN.md) — test matrix, baseline observations and caveats.
- [`patches/README.md`](patches/README.md) — patch-specific rationale and scope.
- [Issue #1](https://github.com/Johnny-Kao/codex-writer-lock-research/issues/1) — initial experimental log.

For reproduction, inspect the workflow's pinned upstream SHA and commands rather than applying this patch against an arbitrary current Codex release.

### 6. Impact, limitations, and next decision

**Demonstrated improvement:** an explicitly relinquished, idle thread can transfer writer ownership promptly without dropping the single-writer check. This reduces avoidable blocked handoffs in the tested **cross-process** case.

**Not demonstrated:** that unexpected iPhone app suspension, actual Remote Control transport/session routing, or reconnect during an active model turn follows precisely the tested path. An abrupt **server process exit** and a **client-only network disconnect** are distinct failure modes. The single-daemon WebSocket control passed, but is not equivalent to real mobile Remote Control end-to-end validation.

**Current recommendation:** treat this as a validated **experimental patch and reproducible research report**, keep the research PR in Draft, and decide separately whether to (a) build an unpatched same-daemon control and realistic active-turn/drop scenarios, (b) discuss the exact lifecycle design with upstream maintainers, or (c) prepare an upstream proposal if contribution policies permit. Do not claim full mobile incident resolution or deploy automatically.

### 7. Safety and provenance

- No production Codex daemon, personal session, account token, or M5 development machine was used for the GitHub CI regressions.
- The initial baseline research used a disposable local `CODEX_HOME`; all published fixtures are synthetic.
- Never remove live writer-lock files or bypass single-writer enforcement.
- No paid or self-hosted GitHub Actions runner required.
- This project is independent and is **not affiliated with or endorsed by OpenAI**.

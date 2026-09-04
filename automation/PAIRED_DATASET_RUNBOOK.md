# Paired same-task automation runbook

## Objective

Build and evaluate a blinded differential-replay experiment using real ShowUI actions. Within the same task families, distinguish application regressions from agent-or-harness failures by replaying the candidate trajectory on a known-good reference application.

## Operating constraints

- Treat `work/paired_automation_state.json` as the single source of truth.
- Perform only the next safe phase, then checkpoint and end the turn.
- Keep active work per heartbeat under about 20 minutes. Never wait on a cloud job or a local process for more than 60 seconds.
- Do not spawn subagents.
- Preserve all existing user changes and never expose credentials, tokens, signed URLs, or the cloud project ID in committed files or messages.
- Never launch a cloud job if a matching job may already be active.
- Use at most three cloud attempts total. Never retry the same failure fingerprint twice.
- Actual provider billing is authoritative; estimates must remain labeled as estimates.

## Experimental design

1. Add several preregistered variants within each task family so task identity cannot directly reveal the failure class.
2. Freeze tasks, seeds, hidden candidate conditions, prompt, runtime caps, labels, and metrics before test execution.
3. Run ShowUI only on the candidate application and preserve every raw output, parsed action, screenshot, latency, and stop reason.
4. Replay the exact candidate actions locally from the same initial state on the known-good reference application. Do not invent a corrected action.
5. Predict one of `application_regression`, `agent_or_harness`, or `ambiguous` without access to the hidden condition, fault name, backend state, or gold label.
6. Establish gold separately from hidden execution logs, including whether an application fault was actually reached and causally affected the failure.
7. Report overall and per-task confusion matrices, application-regression precision/recall, false bug report rate, ambiguous rate, confidence intervals, trace gallery, runtime, and costs.

## State phases

- `implementation`: implement task variants, manifests, exact-action reference replay, blind differential diagnosis, artifacts, and tests.
- `audit`: run the complete local suite, inspect label isolation and task/condition balance, freeze the config, and prepare a capped DataSphere job.
- `launch_ready`: confirm no matching active job, launch exactly one job, record its ID and attempt number, and end immediately.
- `cloud_running`: inspect status once. If still running, change nothing and end.
- `repair_pending`: inspect the bounded failure log, record a fingerprint, make only an understood fix, run relevant tests, then return to `launch_ready`. Repeated fingerprints or uncertain fixes become `blocked`.
- `download_ready`: download the completed outputs once and validate archive safety, episode/call counts, hashes, and completion state.
- `analysis_ready`: compute the preregistered metrics, plots, trace gallery, README/report updates, full tests, and final package.
- `done`: verify deliverables once; later heartbeats immediately exit.
- `blocked`: record the exact blocker and required user action; do not improvise or spend further cloud budget.

## Locking and idempotency

Before changing state, write an atomic lock containing the phase and timestamp. If another lock is less than 60 minutes old, exit without work. A stale lock may be cleared only after inspecting state and existing processes/jobs. Every external mutation must be preceded by a read-only existence/status check and followed by an atomic state update.

## Cloud failure policy

- A successful job is never relaunched.
- A running or indeterminate job is never duplicated.
- On failure, store a concise fingerprint based on the root error, not volatile timestamps.
- Retry only after a local fix and relevant tests pass.
- Stop after three total attempts or the first repeated fingerprint.


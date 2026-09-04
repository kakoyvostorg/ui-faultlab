# Interview demo handoff

## Primary paired traces

1. `delete_01` — application regression. The candidate deletion fails, while the exact same three ShowUI clicks delete the event on the reference.
2. `attendee_02` — agent or harness. Candidate and reference receive the same wrong actions and fail identically; the application is not blamed.
3. `create_02` — ambiguous. A save fault is reached, but the action sequence also fails on the reference, so the system abstains from a causal claim.
4. `attendee_01` — the sole attribution error. Causal gold is ambiguous, but identical terminal pixels lead the blind rule to choose agent or harness.

Open `report/paired_results/trace_gallery.html` to show all four candidate/reference comparisons.

## Three strongest traces

1. `ep_c5e089982aee18ad` — `add_attendee`, `wrong_candidate`, agent error. The terminal and passive views blame the application; replaying the intended field focus produces a different screenshot and corrects attribution.
2. `ep_07a39d02bc367244` — `delete_event`, `duplicate_action`, agent error. The duplicate prevents confirmation; one replay of the intended confirm transition separates it from a deletion defect.
3. `ep_7a3ca36e5fdc0d86` — `delete_event`, `confirmation_transition_bug`, application bug. The modal visibly closes but the event remains; the same-condition replay reproduces the transition and supports an app-bug label.

The gallery includes one representative case for each of the six injected fault mechanisms.

## 60–90 second pitch (Russian)

После описания задач команды мне стало интересно проверить практический риск: если визуальный агент сообщает, что UI-тест упал, как понять, сломано приложение или ошибся сам агент? Я собрал воспроизводимый Mini Calendar и сначала проверил механику на контролируемых ошибках, а затем сделал основной paired-прогон с реальным ShowUI-2B.

Я заранее зафиксировал 24 кейса: четыре task family, три split и в каждой ячейке clean и faulted candidate. ShowUI видел только инструкцию и скриншоты и сделал 122 реальных вызова. После каждого candidate-run я без исправлений воспроизводил те же parsed actions на known-good reference. Диагностика видела только две траектории; fault type и gold были изолированы.

Candidate упал на 21 из 24 задач. Paired replay правильно классифицировал 20 из 21 падений. Он нашёл все три causally decisive application regressions и ни разу не обвинил приложение в остальных 18 падениях; terminal-only comparator ошибочно обвинил бы приложение во всех 18. Семь раз метод честно вернул ambiguous, потому что агент провалился и на reference. Поэтому мой основной результат — не «95% на всех GUI», а executable attribution protocol с controlled replay, abstention, leakage tests и полными machine-readable artifacts.

## Live demo sequence

1. Run `.venv/bin/pytest -q`.
2. Open `report/paired_results/trace_gallery.html` and show `delete_01`, `attendee_02`, and `create_02`.
3. Open `report/paired_results/accuracy_comparison.svg` and the confusion matrix.
4. Open `artifacts/paired_metrics.json` and `artifacts/paired_preregistration.json` to show frozen inputs and generated metrics.
5. If time remains, open the controlled gallery to explain how the replay mechanism was unit-tested before the learned-agent run.

## Personal verification before the interview

- Open the gallery in the exact laptop/browser used for the interview and confirm images render at a comfortable zoom.
- Rehearse the distinction between terminal evidence, passive trajectory evidence, and one active replay.
- Be ready to say that the scripted actor is an oracle fixture, not a learned baseline.
- Separate task success from attribution: only 3/24 paired candidate tasks succeeded, while attribution is evaluated on the other 21 failures.
- Say explicitly that there are only 3 decisive application-regression cases; 3/3 precision has a wide 43.9%–100% Wilson interval.
- Report cloud cost as a runtime-derived estimate, not a confirmed charge: 47.93–66.57 RUB for the paired job and 295.21 RUB conservatively across all ledger rows.
- Keep the synthetic/generalization limitation explicit.

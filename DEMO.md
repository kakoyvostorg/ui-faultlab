# Interview demo handoff

## Three strongest traces

1. `ep_c5e089982aee18ad` — `add_attendee`, `wrong_candidate`, agent error. The terminal and passive views blame the application; replaying the intended field focus produces a different screenshot and corrects attribution.
2. `ep_07a39d02bc367244` — `delete_event`, `duplicate_action`, agent error. The duplicate prevents confirmation; one replay of the intended confirm transition separates it from a deletion defect.
3. `ep_7a3ca36e5fdc0d86` — `delete_event`, `confirmation_transition_bug`, application bug. The modal visibly closes but the event remains; the same-condition replay reproduces the transition and supports an app-bug label.

The gallery includes one representative case for each of the six injected fault mechanisms.

## 60–90 second pitch (Russian)

После описания задач команды мне стало интересно проверить один практический риск: если визуальный агент сообщает, что UI-тест упал, как понять, сломано приложение или ошибся сам агент? Я собрал небольшой воспроизводимый стенд Mini Calendar с четырьмя многошаговыми задачами, тремя ошибками агента и тремя реальными дефектами переходов приложения. Агент получает только скриншоты; DOM, backend state и gold fault labels остаются у evaluator-а.

На 24 контролируемых failed episodes диагностика только по финальному экрану имела precision bug reports 12 из 24, то есть 50%, и ошибочно считала багом приложения все 12 ошибок агента. Полная траектория подняла precision до 12 из 16, или 75%. Один направленный replay подозрительного действия дал 12 из 12, но Wilson-интервал всё ещё широкий — от 75.8% до 100% — и это синтетический стенд, поэтому я не заявляю generalization. Самое полезное здесь не идеальное число, а executable protocol: snapshot, causal probe, label-isolation tests и machine-readable artifacts. Реальный ShowUI baseline я честно остановил на model gate: на доступном host не было нужного runtime и подтверждённого DataSphere доступа, поэтому VLM-результатов и расходов я не выдумывал.

## Live demo sequence

1. Run `.venv/bin/pytest -q`.
2. Open `report/failure_gallery/index.html` and show the three traces above.
3. Point to observed vs counterfactual screenshots and the terminal/trajectory/active predictions.
4. Open `artifacts/tables/metrics.json` to show that the report is generated, not hand-edited.
5. If time permits, run one clean local episode and rebuild the report.

## Personal verification before the interview

- Open the gallery in the exact laptop/browser used for the interview and confirm images render at a comfortable zoom.
- Rehearse the distinction between terminal evidence, passive trajectory evidence, and one active replay.
- Be ready to say that the scripted actor is an oracle fixture, not a learned baseline.
- Do not claim a ShowUI result; the model gate recorded zero model inferences.
- If a DataSphere run is still desired, provide the exact project ID and authenticated access first; verify price/balance and the 100 RUB reserve before launch.
- Keep the synthetic/generalization limitation explicit.


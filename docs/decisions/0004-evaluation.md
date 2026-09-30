# 0004: How the scanner is scored

Status: accepted

- **Per-type precision and recall, plus a micro-average.** Micro means all counts are summed first,
  so every column weighs the same. Macro (average of per-type scores) would let one tiny type
  dominate.
- **A wrong type counts twice:** a miss for the real type and a false alarm for the guessed one.
- **Undefined is shown as `n/a`, not 0%.** A type the scanner never predicted has no precision.
  Recall still shows 0%, which is the honest number for person names.
- **Unlabeled columns are ignored and counted, not penalised.** Pointing `evaluate` at a database
  with a partial answer key should not produce fake false alarms.
- **Answer key = the synthetic generator's labels.** This measures whether the rules do what they
  claim, not how they behave on real data. The README says so.
- **Test guard:** `test_demo_data_has_no_false_alarms_and_misses_only_names` fails if a change
  silently makes the published numbers worse.

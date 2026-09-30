# 0007: Local LLM second opinion

Status: accepted. The code is tested with a fake model and a stub server; results with a real
model are not measured yet.

- **Scope:** only text columns the rules did not flag, and only one label, `person_name`. Rules
  cannot find names; every other type has a validator that does better. A label is added only
  together with a way to measure it.
- **No masking, and this reverses the earlier plan.** The roadmap said "masked samples". Masking a
  name defeats the purpose of finding names. Privacy comes from other controls instead:
  - the model must be on this machine: non-local addresses are refused unless
    `--allow-remote-llm` is passed, redirects are not followed, and proxy settings from the
    environment are ignored, so samples cannot be rerouted through a third party;
  - at most 15 distinct values per column are shown (3 questions x 5 values);
  - the answer is constrained to a small JSON schema and is only ever a label, never an action.
- **Voting over different samples.** Each column is asked about 3 times with different values.
  The share that agrees becomes the confidence, and 60% (2 of 3) flags the column. A model has no
  calibrated confidence; this is a crude but honest substitute. Unusable replies count as votes
  that did not agree, and are reported as a warning.
- **Sample values are untrusted input.** They are passed as a JSON string, never mixed into the
  instructions, and the prompt tells the model to ignore instructions found in them. This lowers
  the risk of prompt injection; it does not remove it. The worst outcome is a wrong label.
- **The gate never uses the model.** `check` and `catalog` ignore `--llm`: a build that can
  fail differently on every run gets disabled. Model findings are marked `source: llm` and are
  for exploration and for `evaluate`.
- **Measured side by side.** `evaluate --llm` prints rules alone and rules plus model. The demo
  data has decoys that read like surnames (`company_name`, `product_name`), so a model that guesses
  from the look of a word is punished in precision.
- **Standard library HTTP, no new dependency.** One POST request does not justify a client library.
- **Known limits:** temperature 0 and a fixed seed make runs close to repeatable, not identical
  across model versions. Small models may fail at this task; the evaluation exists to show it.

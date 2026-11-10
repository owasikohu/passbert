# Context extraction experiment v3

This is an offline annotation experiment, not a deployed student-model change.
The frozen corpus and the first blind-review round remain unchanged.

The original 80 training-site examples were replayed from their Common Crawl
archive locators in memory. All 80 baseline signatures and all 232 field
positions matched. No raw HTML, original URLs, values, cookies or credentials
were saved or uploaded. Validation/test sites are excluded.

The new closed-vocabulary view uses complete English words and identifier
boundaries, Japanese semantic aliases, and separate markers for labels,
placeholders, identifiers, descriptions and fieldset legends. Text from control
contents, hidden ancestors and editable areas is excluded. Orphan body groups
receive no page-global context. Empty field hints increased from 79 to 88;
removing substring matches can remove misleading evidence as well as coverage.

Run:

```sh
.venv/bin/python -m scripts.replay_context
.venv/bin/python -m scripts.prepare_blind_review \
  --slug passbert-context-review-qwen38-v3 \
  --root artifacts/context-review-v3 \
  --requests artifacts/context-review-v3/requests.jsonl \
  --overlays artifacts/context-review-v3/overlays.jsonl
.venv/bin/kaggle kernels push -p artifacts/context-review-v3/kernel --accelerator NvidiaTeslaT4
.venv/bin/python -m scripts.finish_context_review
```

The private Kaggle job is `owasikohu/passbert-context-review-qwen38-v3`.
It uses the same pinned Qwen3.8-27B Q6 weights, system prompt, decoding settings,
eight controls and record ordering as round one. Only corpus feature views
change. The collector downloads outputs, validates hashes and controls, then
writes `artifacts/context-review-v3/paired-comparison.json`. A local watcher
requires WSL to remain running; the collector command can resume after shutdown.

The comparison rejects mismatched IDs, field counts, model/runtime/prompt
settings and control inputs. It reports changed labels and abstentions, not
accuracy. Reduced abstention does not demonstrate correctness. Changed cases
need adjudication, especially unsupported password/OTP/captcha interpretations.
No labels are promoted to gold or training data. Comparing these outputs with
Zap's old view is not a fair model-only benchmark. Retraining and Firefox
integration are subsequent experiments after extraction and labels are reviewed.

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

## Completed paired run and evidence audit

The Kaggle run completed and outputs were retrieved before the WSL interruption.
All eight controls passed and all 80 corpus responses were valid. Purpose labels
changed on 13 forms; field labels changed at 46 of 232 positions. Unknown purpose
labels increased from 7 to 10, while unknown fields decreased from 78 to 66.
These measurements describe model behavior, not accuracy.

The union of changed purposes/fields contains 28 forms, including nine with
changed password, OTP or CAPTCHA field labels. Two new-password predictions
have only autocomplete evidence on otherwise empty text inputs. One OTP
prediction has only a generic code identifier. Those cases are held for review.
An earlier password-change/new-password guess from a generic change/confirmation
fragment became unreviewable after removing global context; this is consistent
with more conservative behavior but has not been adjudicated against a gold label.

Run `.venv/bin/python -m scripts.audit_context_review` to rebuild the evidence
audit and `artifacts/context-review-v3/adjudication-queue.jsonl`. The collector
now runs this step after paired comparison. The audit validates controls and
record alignment, keeps original opinions, and routes 27 forms to manual review.
The other 53 pass these limited rules and remain weak candidates. Passing rules
does not establish label correctness or agreement with Zap. All 80 retain
`verified=false` and `training_eligible=false`.

Rules require actual password evidence beyond autocomplete, evidence of the
password role, and specific OTP/CAPTCHA cues beyond a generic code. Conflicting
password autocomplete or OTP/CAPTCHA cues trigger review. These are conservative
routing checks, not a replacement classifier; they can reject valid examples.
The queue prioritizes sensitive changes, then other changed cases, then the
remaining cases. No new GPU run or student retraining was launched for this audit.

Before scaling to the remaining training sites, adjudicate the 28 changed forms
and sample stable candidates to estimate routing errors. Ambiguous filtered
views stay unknown; do not invent gold from model consensus. Any subsequent
large-label run must keep validation/test sites excluded, preserve per-label
provenance and use the same extraction view for its student inputs. Evaluation
against Zap requires independent held-out labels and matched available evidence.

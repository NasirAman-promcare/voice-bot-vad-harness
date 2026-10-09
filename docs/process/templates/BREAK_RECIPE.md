Break recipe: one per must-catch behaviour at `tests/aqis_lab/breaks/<WP>/MC-<nn>-<slug>.patch`.

A recipe is a unified diff (as produced by `git diff`) against the WP's code, preceded by header lines that start with `# `. Git ignores text before the first `diff --git` line, so the file applies with `git apply`.

```text
# MC: 3
# behaviour: corpus-level WER is total errors over total reference words, never the mean of per-clip WERs
# expect-fail: tests/aqis_lab/scoring/test_wer.py::test_FR_0_3_05_corpus_wer_is_total_errors_over_total_words
# expect-fail: tests/aqis_lab/scoring/test_wer.py::test_FR_0_3_05_mean_of_clip_wers_reported_separately
diff --git a/aqis_lab/scoring/wer.py b/aqis_lab/scoring/wer.py
--- a/aqis_lab/scoring/wer.py
+++ b/aqis_lab/scoring/wer.py
@@ ... @@
 (the smallest change that breaks exactly this behaviour)
```

Rules:
- The break must be realistic: the kind of mistake a later change could make, not a syntax error or a deleted file.
- Every `expect-fail` test must fail with the recipe applied; a different test failing does not count.
- A recipe that no longer applies is reported as broken, never as caught. Update it in the WP that changed the code (allowed as an add-cases kind of change).
- The break suite runs each recipe in a throwaway worktree; CI runs a WP's recipes on its pull requests and all recipes nightly on `main`.

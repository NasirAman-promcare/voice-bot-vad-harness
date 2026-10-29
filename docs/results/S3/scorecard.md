# Sprint 3 scorecard (WP-1.3)

Config hash `4ac9f213`, seed 20261102.

## Cascade

Gate: pooled target WER <= 12.00% with <= 35% of turns sent to the heavy model. The perfect gate (`oracle`) is an upper bound, not a policy.

- a practical policy meets the gate: FAIL

## Fine-tuning pilot

Gates: drug recall >= 75% on medical clean and phone; us_conv WER up by at most 0.5% absolute.

- drug recall on medical: FAIL
- us_conv non-regression: FAIL

  - medical/clean: drug recall 57.3% -> 63.8%
  - medical/phone: drug recall 52.1% -> 57.9%
  - us_conv/clean: WER 11.06% -> 13.19% (change +2.13%)
  - us_conv/phone: WER 12.82% -> 15.51% (change +2.68%)

## Prompt biasing

See prompt.csv: each biased row is paired with Sprint 1's own prediction of the same model.


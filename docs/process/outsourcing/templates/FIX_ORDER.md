# Fix order template

The relay builds fix orders automatically from failed checks; Claude writes one by hand only for audit findings on outsourced code (surgical-fix step 4).

```text
# FIX <n> for <WO-ID>

Your previous answer did not pass these checks. Fix the root cause; do not special-case test inputs.

## Failed checks
1. <check name>: <one-line summary>
   <trimmed output: the first 20 and the last 40 lines, at most 120 lines for all checks together>

## Audit findings (only when Claude sends this by hand)
- <finding ID> <severity>: <finding, with file:line and the required behaviour>

## Files you may change
- <subset of the work order's outputs>

## Rules
- Return only the files you change, each complete, in RETURN_FORMAT.md form, followed by the DOD table for the items affected.
- Do not touch any other file, and never the read-only tests.
- If the failure shows the work order itself is wrong, return a QUESTIONS block instead.
```

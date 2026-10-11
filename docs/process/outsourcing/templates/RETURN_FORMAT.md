# Return format (machine-parsed; follow it exactly)

Your whole answer is plain text in this order. Marker lines stand alone on their line, with nothing before or after them.

1. A manifest:

```text
=== MANIFEST ===
| path | action | purpose |
| --- | --- | --- |
| tools/example/module.py | create | one line |
=== END MANIFEST ===
```
`action` is `create` or `replace`. List every file you return, in the order you return them.

2. Each file, whole, once:

```text
=== FILE: tools/example/module.py ===
<the complete file content, from the first line to the last>
=== END FILE ===
```
- The path is exactly as written in the work order's `outputs`.
- You may wrap the content in one fenced code block right after the FILE marker; the importer removes one surrounding fence.
- No partial files, no diffs, no "rest of the file unchanged", no "..." lines standing for omitted code. The importer rejects these and the attempt counts as failed.
- On a first answer, every path that the request's `THIS STEP` block names appears exactly once (without a step block: every path in `outputs`). On a fix order, return only the files you changed, each complete.

3. The Definition of Done table:

```text
=== DOD ===
| item | met at (file:line) | how |
| --- | --- | --- |
| D1 | tools/example/module.py:42 | one line |
=== END DOD ===
```

4. Questions, only when you cannot proceed without an answer. If present, return no FILE blocks at all:

```text
=== QUESTIONS ===
1. <the question, what you found, and the options you see>
=== END QUESTIONS ===
```

Nothing else: no greetings, no summaries, no explanations outside these blocks.

The relay removes one code fence that wraps the whole answer; anything else outside the blocks is refused.

It also removes a code fence wrapped tightly around a single block: a fence line directly before the block’s opening marker and its closing line directly after the block’s END marker.

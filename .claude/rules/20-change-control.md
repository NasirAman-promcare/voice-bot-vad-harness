# Change control and regression protection

Before editing any existing file:
1. Read its module header (standard in `docs/process/CHANGE_CONTROL.md`) and the rows in `docs/capabilities/REGISTRY.md` that point to it.
2. Write down the exact functions or classes you will change. That list is your change budget; it must match the approved plan.
3. Run the file's tests and its linked capability tests before changing anything, and record the result.

While editing:
- Change only functions in the change budget. Keep all other code byte-identical.
- Never remove, rename or weaken a capability listed in a header or the registry. If a fix seems to need that, stop and ask.
- Never "clean up" unrelated code, formatting or imports in files you touch.

After editing:
- Re-run the file's tests and every linked capability test; all must pass.
- Update the header's change log and, if behaviour changed, the registry row.
- Check `git diff --stat` and `git diff -U0`: changes must sit inside the change budget.

Protected paths are enforced by hooks and permission rules. Editing a guarded path needs an owner approval file listing it (`ALLOW-EDIT:`). Paths marked NEVER cannot be unlocked by you at all.

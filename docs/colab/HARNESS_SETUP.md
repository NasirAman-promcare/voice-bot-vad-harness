# Harness setup on Google Colab

These cells replace the manual download, extract and install cells for the existing VAD harness (WP-0.0 round 2, FR-0.0-13). They clone the repository with your `GITHUB_TOKEN` Colab secret, then run the one provisioning command, `bash aqis_lab/deploy/harness_provision.sh`.

**What gets installed.** Provisioning installs:
- the system packages `git-lfs`, `libc++1` and `libopus0`;
- `.venv-harness` on the Colab Python;
- the `corpus-v1` clips, taken from git at their pinned commit;
- the FireRedVAD Stream-VAD weights from Hugging Face.

Every item is verified by SHA-256 or commit, and the run ends with a PASS/FAIL table.

**The token is used for the clone command only.** It goes into a one-off `http.extraHeader` option on that command. It never goes into `.git/config`, the remote URL, a credential helper or an environment variable, and cell 3 proves it. If the clone fails, cell 2 raises an error that names only the branch and the repository. The command line is never shown, because it carries the token.

**Platform.** The harness needs Linux x86_64, which standard Colab runtimes are. TEN VAD ships no Arm binary, so on any other machine provisioning stops at once with a `platform | FAIL` row that gives this reason.

**Before you start:** in Colab, open the key icon (Secrets), make sure `GITHUB_TOKEN` exists (read-only "Contents" access to this repository) and that notebook access is allowed. A CPU runtime is enough.

## Cell 1: settings
```python
REPO = "https://github.com/NasirAman-promcare/voice-bot-vad-harness.git"
BRANCH = "main"  # the branch to provision; OC-0.0-01 below says which branch to use before a merge
WORKDIR = "/content/voice-bot-vad-harness"
```

## Cell 2: clone with the secret, used for this command only
```python
import base64
import os
import subprocess

from google.colab import userdata

token = userdata.get("GITHUB_TOKEN")
header = "Authorization: Basic " + base64.b64encode(("x-access-token:" + token).encode()).decode()
# No check=True: its error would print the whole command line, header included. Keep only the exit code.
exit_code = subprocess.run(["git", "-c", "http.extraHeader=" + header, "clone", "--branch", BRANCH, REPO, WORKDIR],
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0")).returncode
del token, header
if exit_code != 0:
    raise RuntimeError(f"git clone of branch {BRANCH} from {REPO} failed (exit {exit_code}); git's own message "
                       "is above. Check BRANCH in cell 1 and the GITHUB_TOKEN secret.")
print("cloned", BRANCH)
```

## Cell 3: prove the token was not kept
```python
config = subprocess.run(["git", "-C", WORKDIR, "config", "--list", "--show-origin"],
                        capture_output=True, text=True, check=True).stdout
remote = subprocess.run(["git", "-C", WORKDIR, "remote", "get-url", "origin"],
                        capture_output=True, text=True, check=True).stdout.strip()
assert "extraheader" not in config.lower(), "an authorization header is in git config"
assert remote == REPO, "the remote URL changed: " + remote
print("OK: no token in git config or in the remote URL")
```

## Cell 4: uv (pinned version, only if Colab does not already have uv)
```python
import shutil

if shutil.which("uv") is None:
    subprocess.run(["pip", "install", "uv==0.8.17"], check=True)
print(subprocess.run(["uv", "--version"], capture_output=True, text=True, check=True).stdout)
```

## Cell 5: provision and write the report
```python
proc = subprocess.run(["bash", "aqis_lab/deploy/harness_provision.sh"], cwd=WORKDIR, capture_output=True, text=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=WORKDIR, capture_output=True, text=True,
                        check=True).stdout
report = (proc.stdout + proc.stderr + "\nexit code: " + str(proc.returncode)
          + "\ngit status --porcelain: [" + status + "]\n")
with open("/content/colab_harness_provision.txt", "w", encoding="utf-8") as handle:
    handle.write(report)
print(report[-5000:])
```

## Cell 6: download the report
```python
from google.colab import files

files.download("/content/colab_harness_provision.txt")
```

## Owner-run check OC-0.0-01
This check runs before the merge. Until then, the provisioning script exists only on the WP-0.0 pull request branch, not on `main`.
1. In cell 1, set `BRANCH = "claude/hopeful-noether-yinc4e"` (the WP-0.0 pull request branch).
2. Run cells 1 to 6 on a fresh runtime.
3. Commit the downloaded file to the pull request branch as `docs/environment/colab_harness_provision.txt`.

Expected result:
- every row PASS in the table, with `torch` shown as `INFO | not installed, decision R2-3`;
- `RESULT: PASS` and `exit code: 0`;
- `git status --porcelain: []`.

A second run of cell 5 should show `Downloads this run: 0`.

**Wrong branch.** If `BRANCH` names a branch that does not exist, cell 2 stops with git's message `fatal: Remote branch <name> not found in upstream origin`, followed by `RuntimeError: git clone of branch <name> from https://github.com/... failed (exit 128)`. Nothing else is shown. Fix `BRANCH`, delete the `WORKDIR` folder if it exists, and run cell 2 again.

If a row says FAIL, commit the report anyway and ask Claude to run `/surgical-fix docs/environment/colab_harness_provision.txt`.

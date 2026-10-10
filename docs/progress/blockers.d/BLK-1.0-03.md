# BLK-1.0-03 — Full Colab GPU output of dev_bootstrap.sh --gpu (DEBT-032)
Status: OPEN
WP: WP-1.0
Owner capability: COMPUTE
Raised: 2026-10-10
Session: https://claude.ai/code/session_01MdrFmVCBzGrRzg4n2dVGRx
Unblocks: WP-1.0 (FR-1.0-11, DEBT-032)
Time needed: 15 minutes, on a Colab GPU runtime
Loop: none

What I need: the complete output of `bash aqis_lab/deploy/dev_bootstrap.sh --gpu` from a Colab GPU runtime, committed as `docs/progress/WP-0.8/OC-0.8-03_bootstrap_gpu_full.txt` on the WP-1.0 branch.

Why: DEBT-032's fix is that output. It must show the line `OK: GPU extras installed: requirements/aqis_lab/phase0-gpu.txt sha256 …`, which the current one-line note lacks. This cloud VM has no GPU and must not run the Colab GPU path.

What I tried:
- Read `docs/progress/WP-0.8/OC-0.8-03_bootstrap_gpu.txt`. It is a single summary line quoting the CPU lock hash, as DEBT-032 says.
- Read `aqis_lab/deploy/dev_bootstrap.sh` line 114, which prints the expected `OK: GPU extras installed` line only on a successful `--gpu` run.

Options:
1. Run it on Colab with the setup cells you already use. (recommended)
2. Keep DEBT-032 open and move it to a later WP. That is a debt move only you can approve.

Exact steps:
1. In Colab, choose Runtime > Change runtime type > T4 GPU (or any GPU).
2. Run cells 1 to 4 of `docs/colab/HARNESS_SETUP.md` (clone with your `GITHUB_TOKEN` secret, then uv). In cell 1 set `BRANCH = "claude/wp-1-0-operating-model-v2"`.
3. Run this cell: `import subprocess; p = subprocess.run(["bash", "aqis_lab/deploy/dev_bootstrap.sh", "--gpu"], cwd=WORKDIR, capture_output=True, text=True); open("/content/OC-0.8-03_bootstrap_gpu_full.txt", "w").write(p.stdout + p.stderr + "\nexit code: " + str(p.returncode) + "\n"); print(p.stdout[-3000:], p.stderr[-2000:], p.returncode)`
4. Download `/content/OC-0.8-03_bootstrap_gpu_full.txt` from the Files pane.
5. On GitHub, switch to branch `claude/wp-1-0-operating-model-v2`, open `docs/progress/WP-0.8/` and choose Add file > Upload files. Upload the file and commit to that branch.
6. Tell this session "GPU output uploaded".

Meanwhile: all other WP-1.0 work. The DEBT-032 test (`test_FR_1_0_11_debt032_*`) is written against the expected line and stays failing until the file arrives.

Owner answer:

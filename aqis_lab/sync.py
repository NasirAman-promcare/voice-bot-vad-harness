"""Copy the results store one way to AQIS_LAB/results on Google Drive with `rclone copy --immutable`.

CAPABILITIES:
  CAP-SYNC-001: run_sync() checks the store, rclone (at least 1.60.1), that the configured remote exists and that <remote>:AQIS_LAB/results already exists (the lab never creates AQIS_LAB), then runs only `rclone copy <store> <remote>:AQIS_LAB/results --immutable --checksum --no-update-modtime` excluding .partial and .lock files (plus --dry-run when asked): remote files are never deleted, and a remote file that differs is never replaced but reported [tests: test_FR_0_6_05_copies_store_to_aqis_lab_results, test_FR_0_6_05_never_deletes_remote_files, test_FR_0_6_05_never_replaces_a_remote_file, test_FR_0_6_05_dry_run_changes_nothing, test_FR_0_6_05_command_is_copy_only, test_FR_0_6_05_partial_files_not_copied, test_FR_0_6_05_rclone_version_minimum]
  CAP-SYNC-002: a missing rclone, a remote that is not configured, a missing AQIS_LAB/results on the remote or a missing store is a SyncUsageError whose message points to the runbook section to follow; when listing <remote>:AQIS_LAB fails for another reason than a missing folder (rclone exit 3), sync shows rclone's own message and exits 1, and a missing folder's message includes rclone's message too; an rclone copy that runs past the time limit is stopped and is a SyncFailed (exit 1) (DEBT-015) [tests: test_FR_0_6_05_missing_remote_points_to_runbook, test_FR_0_6_05_missing_rclone_points_to_runbook, test_FR_0_6_05_refuses_when_remote_results_folder_missing, test_FR_0_6_05_missing_store_exit_2, test_FR_0_6_05_failed_remote_listing_shows_rclone_message, test_FR_0_6_05_rclone_timeout_is_an_error]
INPUTS AND OUTPUTS: config/aqis_lab/oracle.yaml (remote name, store path) and --dry-run in; rclone's messages and a
  summary on stdout; SyncUsageError (exit 2) or SyncFailed (exit 1).
CONTRACTS: Drive layout AQIS_LAB/{packs,models,results,logs} (WP-0.5); store layout in docs/results/RESULTS_STORE.md.
INVARIANTS:
  - One way only: the store is read, Drive is written; the only rclone command that writes is `copy`, built from
    constants, and this module names no rclone command or flag that deletes or moves files.
  - The destination is fixed: <remote>:AQIS_LAB/results.
NOT IN SCOPE:
  - Configuring rclone or scheduling the nightly run (docs/oracle/ORACLE_RUNBOOK.md).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-05 created.
  2026-09-30 WP-0.7 DEBT-015 (2, 3): _check_destination shows rclone's message when `rclone lsf` fails (exit 1
    unless rclone says the folder is missing); run_sync turns an rclone copy timeout into SyncFailed
    (test_FR_0_6_05_failed_remote_listing_shows_rclone_message, test_FR_0_6_05_rclone_timeout_is_an_error).
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

from aqis_lab import oracle_config
from aqis_lab.results import store

MIN_RCLONE = (1, 60, 1)
RUNBOOK = "docs/oracle/ORACLE_RUNBOOK.md"
AQIS_FOLDER = "AQIS_LAB"
RESULTS_FOLDER = "results"
COPY_FLAGS = ("--immutable", "--checksum", "--no-update-modtime", "--exclude", "*.partial", "--exclude",
              store.LOCK_FILE, "-v")
TIMEOUT_S = 6 * 3600
VERSION_RE = re.compile(r"^rclone v(\d+)\.(\d+)\.(\d+)", re.M)
IMMUTABLE_RE = re.compile(r"ERROR : (.+?): Source and destination exist but do not match: immutable file modified")


class SyncUsageError(RuntimeError):
    """Sync cannot start: a missing tool, remote, folder or store (exit 2)."""


class SyncFailed(RuntimeError):
    """rclone ran and failed, or refused to replace a remote file (exit 1)."""


def check_rclone_version(text):
    """The (major, minor, patch) of `rclone version` output; SyncUsageError when unreadable or too old."""
    m = VERSION_RE.search(text)
    need = ".".join(map(str, MIN_RCLONE))
    if not m:
        raise SyncUsageError(f"cannot read the rclone version from {text.splitlines()[:1]}; rclone {need} or newer is "
                             f"needed ({RUNBOOK}, section \"Install uv and rclone\")")
    version = tuple(int(x) for x in m.groups())
    if version < MIN_RCLONE:
        raise SyncUsageError(f"rclone {'.'.join(map(str, version))} is too old; rclone {need} or newer is needed "
                             f"({RUNBOOK}, section \"Install uv and rclone\")")
    return version


def copy_command(rclone, store_dir, remote, dry_run):
    """The one rclone command that writes: copy the store to <remote>:AQIS_LAB/results."""
    argv = [str(rclone), "copy", str(store_dir), f"{remote}:{oracle_config.DRIVE_DESTINATION}", *COPY_FLAGS]
    if dry_run:
        argv.append("--dry-run")
    return argv


def _run(argv, timeout=120):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=dict(os.environ))
    except subprocess.TimeoutExpired as exc:
        raise SyncFailed(f"{' '.join(argv[:2])} did not finish within {timeout} s") from exc
    except OSError as exc:
        raise SyncUsageError(f"cannot run {argv[0]}: {exc.strerror or exc}") from exc


def _check_remote(rclone, remote):
    proc = _run([rclone, "listremotes"])
    if proc.returncode != 0:
        raise SyncFailed(f"rclone listremotes failed (exit {proc.returncode}): {proc.stderr.strip()}")
    if f"{remote}:" not in {line.strip() for line in proc.stdout.splitlines()}:
        raise SyncUsageError(f'rclone remote "{remote}" is not configured; set it up as in {RUNBOOK}, section '
                             f'"Configure rclone for Google Drive" (the remote name comes from config/aqis_lab/'
                             f'oracle.yaml, rclone.remote)')


def _check_destination(rclone, remote):
    where = f"{remote}:{AQIS_FOLDER}"
    proc = _run([rclone, "lsf", where, "--dirs-only"])
    not_found = 3                              # rclone's documented exit code for "directory not found"
    if proc.returncode not in (0, not_found):
        raise SyncFailed(f"rclone lsf {where} failed (exit {proc.returncode}), rclone says: {proc.stderr.strip()}; "
                         f"if the Google sign-in of the remote expired, connect it again as in {RUNBOOK}, "
                         f"section \"Configure rclone for Google Drive\"")
    if proc.returncode != 0 or f"{RESULTS_FOLDER}/" not in proc.stdout.splitlines():
        found = f"not found (rclone says: {proc.stderr.strip()})" if proc.returncode != 0 else "has no results folder"
        raise SyncUsageError(f"{where} {found}: {oracle_config.DRIVE_DESTINATION} must already exist on Google Drive; "
                             f"the lab never creates {AQIS_FOLDER} (create it and run `drive layout` on Colab, or see "
                             f"{RUNBOOK}, section \"Configure rclone for Google Drive\")")


def run_sync(config=None, dry_run=False, echo=print):
    """Copy the store one way to Drive (see the module header); returns rclone's exit code 0 on success."""
    cfg = oracle_config.load(config)
    store_dir = store.check_store(cfg.results_store)
    rclone = shutil.which("rclone")
    if rclone is None:
        raise SyncUsageError(f"rclone not found on PATH; install it as in {RUNBOOK}, section \"Install uv and rclone\"")
    version = _run([rclone, "version"])
    if version.returncode != 0:
        raise SyncFailed(f"rclone version failed (exit {version.returncode}): {version.stderr.strip()}")
    parsed = check_rclone_version(version.stdout)
    _check_remote(rclone, cfg.rclone_remote)
    _check_destination(rclone, cfg.rclone_remote)
    echo(f"sync: source {store_dir}")
    echo(f"destination {cfg.rclone_remote}:{oracle_config.DRIVE_DESTINATION}")
    echo(f"rclone v{'.'.join(map(str, parsed))} at {rclone}")
    echo(f"mode {'DRY RUN' if dry_run else 'COPY'} (copy only: remote files are never deleted or replaced)")
    try:
        proc = subprocess.run(copy_command(rclone, store_dir, cfg.rclone_remote, dry_run), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, timeout=TIMEOUT_S, env=dict(os.environ))
    except subprocess.TimeoutExpired as exc:
        output = exc.output.decode("utf-8", "replace") if isinstance(exc.output, bytes) else exc.output or ""
        for line in output.splitlines():
            echo(line)
        raise SyncFailed(f"rclone copy did not finish within {TIMEOUT_S} s and was stopped; run the sync again (it "
                         f"only copies: files already on Google Drive are kept, and what is missing is copied)") from exc
    for line in proc.stdout.splitlines():
        echo(line)
    if proc.returncode != 0:
        refused = IMMUTABLE_RE.findall(proc.stdout)
        if refused:
            raise SyncFailed(f"{len(refused)} file(s) on Google Drive differ from the store and were left as they are "
                             f"(remote files are never replaced): {', '.join(refused)}")
        raise SyncFailed(f"rclone copy failed (exit {proc.returncode}); see its messages above")
    echo("DRY RUN: nothing was copied" if dry_run else "sync complete")
    return 0

"""Source acquisition: download a dataset archive, prove it is the pinned one, and extract only the listed members.

CAPABILITIES:
  CAP-REG-003: fetch_dataset() downloads a dataset's archive into a git-ignored cache with HTTP range resumption (up to five attempts per call, and a .part left by an earlier call is resumed), checks its size, SHA-256 pin and published MD5 before reading any member and deletes it on a mismatch, then extracts only the members matching the dataset's extract patterns (regular files only; an unsafe member name anywhere in the archive, or a link or device among the listed members, is an error) through a staging folder, and writes a completion marker listing every extracted file with its SHA-256; a second call downloads and extracts nothing while the archive and the extracted files still match; extracted_root() returns a completed extraction or raises; on Google Drive it writes only under MyDrive/AQIS_LAB (NFR-0.5-02): the cache and every path it writes are checked before any download, and another Drive path is a FetchError [tests: test_FR_0_4_02_fetch_checks_hash_before_extracting, test_FR_0_4_02_fetch_rejects_wrong_hash_and_keeps_nothing, test_FR_0_4_02_fetch_resumes_partial_download, test_FR_0_4_02_second_fetch_downloads_nothing, test_FR_0_4_02_extracts_only_listed_members_safely, test_FR_0_4_02_members_outside_the_patterns_are_never_written, test_FR_0_4_02_refuses_cache_not_ignored_by_git, test_FR_0_4_02_default_cache_is_ignored_by_git, test_FR_0_4_02_dataset_pins_match_openslr, test_NFR_0_5_02_registry_fetch_refuses_drive_cache_outside_aqis_lab]
INPUTS AND OUTPUTS: a download Dataset (URL, bytes, sha256, md5, extract patterns), the cache folder and the
  repository root in; FetchResult (archive path, extracted root, bytes downloaded, whether it extracted) out;
  FetchError naming the dataset and the problem.
CONTRACTS: datasets.yaml format 1 (docs/data/REGISTRY_FORMAT.md).
INVARIANTS:
  - No member is read before the whole archive matches its pins; a mismatching download is deleted.
  - Nothing is written outside the cache folder, and a cache inside the repository must be ignored by git.
  - The completion marker is written last, so an interrupted extraction is never taken as complete.
NOT IN SCOPE:
  - Turning extracted files into registry rows (aqis_lab/registry/importers.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-02 created.
  2026-09-30 WP-0.7 DEBT-014: fetch_dataset checks the cache, archive, .part, extraction and staging paths with
    aqis_lab.drive.check_write_path before any download (test_NFR_0_5_02_registry_fetch_refuses_drive_cache_outside_aqis_lab).
"""
import hashlib
import http.client
import json
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT_CACHE = "data/raw/aqis_lab"
MARKER = ".aqis-complete.json"
CHUNK = 1 << 20
ATTEMPTS = 5
TIMEOUT_S = 60
PROGRESS_EVERY = 256 << 20


class FetchError(RuntimeError):
    """A dataset could not be downloaded, did not match its pins, or could not be extracted safely."""


class SizeMismatch(FetchError):
    """The server reports a size that differs from the pinned one."""


@dataclass(frozen=True)
class FetchResult:
    archive_path: Path
    extracted_root: Path
    downloaded_bytes: int
    extracted: bool


def pattern_regex(pattern):
    """Anchored regex for an extract pattern: '**' matches across folders, '*' and '?' within one folder."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))


def _safe_member_name(name):
    if not name or name.startswith("/") or "\\" in name or re.search(r"[\x00-\x1f\x7f]", name):
        return False
    return all(part not in ("..",) for part in PurePosixPath(name).parts) and not PurePosixPath(name).is_absolute()


def _log(message):
    print(message, file=sys.stderr, flush=True)


def _check_cache_ignored(cache, repo_root):
    cache = Path(cache).resolve()
    root = Path(repo_root).resolve()
    if cache != root and root not in cache.parents:
        return
    if cache == root:
        raise FetchError(f"cache {cache} is the repository root; use a git-ignored folder such as {DEFAULT_CACHE}")
    top = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], capture_output=True,
                         text=True)
    if top.returncode != 0 or top.stdout.strip() != "true":
        return  # the root is not a git work tree, so nothing in the cache can be committed
    rel = cache.relative_to(root).as_posix()
    probe = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", f"{rel}/probe"], capture_output=True,
                           text=True)
    if probe.returncode == 1:
        raise FetchError(f"cache {rel} is inside the repository but not ignored by git; downloaded corpora must "
                         f"never be committed (use {DEFAULT_CACHE}, which the root .gitignore ignores)")
    if probe.returncode != 0:
        raise FetchError(f"cannot ask git whether {rel} is ignored: {probe.stderr.strip()}")


def _digests(path):
    sha, md5, size = hashlib.sha256(), hashlib.md5(), 0
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            sha.update(block)
            md5.update(block)
            size += len(block)
    return size, sha.hexdigest(), md5.hexdigest()


def _pin_problem(dataset, size, sha, md5):
    if size != dataset["bytes"]:
        return f"download has {size} bytes, datasets.yaml says {dataset['bytes']} bytes"
    if md5 != dataset["md5"]:
        return f"md5 of the download is {md5}, the published md5 is {dataset['md5']} (sha256 {sha})"
    if sha != dataset["sha256"]:
        return f"sha256 of the download is {sha}, datasets.yaml pins {dataset['sha256']}"
    return None


def _download_once(url, part, expected):
    have = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": "aqis-lab-registry-fetch"}
    if 0 < have < expected:
        headers["Range"] = f"bytes={have}-"
    elif have >= expected:
        part.unlink()
        have = 0
    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=TIMEOUT_S)
    except urllib.error.HTTPError as exc:
        raise FetchError(f"{url}: HTTP {exc.code} {exc.reason}") from exc
    with response:
        status = response.status
        if status == 206:
            content_range = response.headers.get("Content-Range", "")
            match = re.fullmatch(r"bytes (\d+)-\d+/(\d+)", content_range)
            if match is None or int(match.group(1)) != have:
                raise FetchError(f"{url}: server resumed at {content_range!r}, expected byte {have}")
            total = int(match.group(2))
            mode = "ab"
        elif status == 200:
            have, mode = 0, "wb"
            length = response.headers.get("Content-Length")
            total = int(length) if length and length.isdigit() else None
        else:
            raise FetchError(f"{url}: unexpected HTTP status {status}")
        if total is not None and total != expected:
            raise SizeMismatch(f"server reports {total} bytes for {url}, datasets.yaml says {expected} bytes")
        written = 0
        next_report = have + PROGRESS_EVERY
        with open(part, mode) as fh:
            while True:
                block = response.read(CHUNK)
                if not block:
                    break
                fh.write(block)
                written += len(block)
                if have + written >= next_report:
                    _log(f"  {have + written:,} of {expected:,} bytes")
                    next_report += PROGRESS_EVERY
    return written


def _download(dataset, part):
    url, expected = dataset["url"], dataset["bytes"]
    part.parent.mkdir(parents=True, exist_ok=True)
    total, errors = 0, []
    for attempt in range(1, ATTEMPTS + 1):
        try:
            total += _download_once(url, part, expected)
        except SizeMismatch:
            raise
        except FetchError:
            raise
        except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
            errors.append(f"attempt {attempt}: {exc}")
            total_now = part.stat().st_size if part.exists() else 0
            _log(f"download of {url} interrupted at {total_now:,} bytes ({exc}); resuming")
            continue
        size = part.stat().st_size
        if size >= expected:
            return total
        errors.append(f"attempt {attempt}: transfer ended at {size} of {expected} bytes")
    raise FetchError(f"{dataset.dataset_id}: download of {url} did not complete after {ATTEMPTS} attempts "
                     f"({'; '.join(errors)}); run the command again to resume")


def _marker_matches(root, archive_sha):
    marker = root / MARKER
    if not marker.is_file():
        return False
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if data.get("archive_sha256") != archive_sha or not isinstance(data.get("files"), list):
        return False
    for name, size, sha in data["files"]:
        path = root / name
        if not path.is_file() or path.stat().st_size != size or _digests(path)[1] != sha:
            return False
    return True


def _extract(dataset, archive, cache, archive_sha):
    target = cache / dataset.dataset_id
    staging = cache / f".{dataset.dataset_id}.partial"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    patterns = [(p, pattern_regex(p)) for p in dataset["extract"]]
    matched = {p: 0 for p, _ in patterns}
    files = []
    try:
        with tarfile.open(archive, mode="r|*") as tf:
            for member in tf:
                if not _safe_member_name(member.name):
                    raise FetchError(f"{dataset.dataset_id}: archive has an unsafe member name {member.name!r}")
                name = PurePosixPath(member.name).as_posix()
                hits = [p for p, rx in patterns if rx.fullmatch(name)]
                if not hits:
                    continue
                if member.isdir():
                    continue
                if not member.isreg():
                    raise FetchError(f"{dataset.dataset_id}: listed member {name!r} is not a regular file")
                for p in hits:
                    matched[p] += 1
                out = staging / name
                out.parent.mkdir(parents=True, exist_ok=True)
                sha = hashlib.sha256()
                source = tf.extractfile(member)
                with open(out, "wb") as fh:
                    for block in iter(lambda: source.read(CHUNK), b""):
                        fh.write(block)
                        sha.update(block)
                files.append([name, member.size, sha.hexdigest()])
        empty = [p for p, count in matched.items() if count == 0]
        if empty:
            raise FetchError(f"{dataset.dataset_id}: extract pattern {', '.join(empty)} matched no member of "
                             f"{archive.name}")
        (staging / MARKER).write_text(json.dumps({"dataset": dataset.dataset_id, "archive_sha256": archive_sha,
                                                  "files": sorted(files)}, indent=1) + "\n", encoding="utf-8")
    except (tarfile.TarError, OSError, EOFError) as exc:
        shutil.rmtree(staging)
        raise FetchError(f"{dataset.dataset_id}: cannot extract {archive}: {exc}") from exc
    except FetchError:
        shutil.rmtree(staging)
        raise
    if target.exists():
        shutil.rmtree(target)
    staging.rename(target)
    return target


def _discard(part, cache):
    """Delete a rejected download and the cache folders it leaves empty."""
    if part.exists():
        part.unlink()
    for folder in (part.parent, cache):
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()


def fetch_dataset(dataset, cache_dir, repo_root):
    """Download (or reuse) and extract a download dataset into cache_dir; see the module header."""
    if dataset["type"] != "download":
        raise FetchError(f"{dataset.dataset_id} is a local dataset; there is nothing to fetch")
    cache = Path(cache_dir)
    _check_cache_ignored(cache, repo_root)
    name = dataset["url"].rstrip("/").rsplit("/", 1)[1]
    archive = cache / "downloads" / f"{dataset.dataset_id}-{name}"
    part = archive.with_name(archive.name + ".part")
    from aqis_lab.drive import DriveError, check_write_path
    from aqis_lab.platform import PlatformError
    try:                                     # NFR-0.5-02: on Google Drive, only under MyDrive/AQIS_LAB
        for path in (cache, archive, part, cache / dataset.dataset_id, cache / f".{dataset.dataset_id}.partial"):
            check_write_path(path)
    except (DriveError, PlatformError) as exc:
        raise FetchError(str(exc)) from exc
    downloaded = 0
    if archive.exists():
        problem = _pin_problem(dataset, *_digests(archive))
        if problem:
            _log(f"{dataset.dataset_id}: kept archive no longer matches ({problem}); downloading again")
            archive.unlink()
    if not archive.exists():
        _log(f"{dataset.dataset_id}: downloading {dataset['url']} ({dataset['bytes']:,} bytes)")
        try:
            downloaded = _download(dataset, part)
            problem = _pin_problem(dataset, *_digests(part))
        except SizeMismatch as exc:
            problem = str(exc)
        if problem:
            _discard(part, cache)
            raise FetchError(f"{dataset.dataset_id}: {problem}; the download was deleted")
        part.rename(archive)
    root = cache / dataset.dataset_id
    if _marker_matches(root, dataset["sha256"]):
        return FetchResult(archive, root, downloaded, False)
    _log(f"{dataset.dataset_id}: extracting {', '.join(dataset['extract'])}")
    return FetchResult(archive, _extract(dataset, archive, cache, dataset["sha256"]), downloaded, True)


def extracted_root(cache_dir, dataset_id):
    """The extraction folder of a fetched dataset; FetchError if it was not fetched completely."""
    root = Path(cache_dir) / dataset_id
    if not (root / MARKER).is_file():
        raise FetchError(f"dataset {dataset_id} is not fetched in {cache_dir}; run: python -m aqis_lab registry "
                         f"fetch {dataset_id}")
    return root

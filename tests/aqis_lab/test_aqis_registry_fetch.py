"""WP-0.4 FR-0.4-02: source acquisition (aqis_lab/registry/fetch.py) and the corpus report.

Downloads are real HTTP transfers from a server on 127.0.0.1 (aqis_packs_testutil.serve); the slow network test
fetches the real archives from www.openslr.org and checks the pins in data/registry/datasets.yaml.
"""
import hashlib
import io
import json
import re
import subprocess
import tarfile

import pytest

from aqis_packs_testutil import ROOT, download_entry, serve, sha256, tar_gz, write_datasets
from aqis_lab.registry import datasets as ds
from aqis_lab.registry import fetch

MEMBERS = [("pkg/README", b"read me\n"), ("pkg/keep/a.txt", b"A" * 3000), ("pkg/keep/sub/b.txt", b"B" * 10),
           ("pkg/other/c.txt", b"C" * 5000)]


def _dataset(tmp_path, url, data, extract=("pkg/README", "pkg/keep/**"), **changes):
    entry = download_entry(url, data, "librispeech", "librispeech", "speech", list(extract), "CC-BY-4.0",
                           split="test-clean")
    entry.update(changes)
    loaded = ds.load_datasets(write_datasets(tmp_path / "datasets.yaml", {"librispeech-test-clean": entry}))
    return loaded.datasets["librispeech-test-clean"]


def _raw_tar(members):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for info, data in members:
            tf.addfile(info, io.BytesIO(data) if data is not None else None)
    return raw.getvalue()


def test_FR_0_4_02_fetch_checks_hash_before_extracting(tmp_path):
    data = tar_gz(MEMBERS)
    with serve({"a.tar.gz": data}) as server:
        dataset = _dataset(tmp_path, f"{server.base}/a.tar.gz", data)
        result = fetch.fetch_dataset(dataset, tmp_path / "cache", tmp_path)
    root = result.extracted_root
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) == [
        ".aqis-complete.json", "pkg/README", "pkg/keep/a.txt", "pkg/keep/sub/b.txt"]
    assert (root / "pkg/keep/a.txt").read_bytes() == b"A" * 3000
    marker = json.loads((root / ".aqis-complete.json").read_text(encoding="utf-8"))
    assert marker["archive_sha256"] == sha256(data)
    assert {f[0]: f[2] for f in marker["files"]}["pkg/keep/sub/b.txt"] == sha256(b"B" * 10)
    assert fetch.extracted_root(tmp_path / "cache", "librispeech-test-clean") == root
    assert result.archive_path.read_bytes() == data


@pytest.mark.parametrize("field", ["sha256", "md5", "bytes"])
def test_FR_0_4_02_fetch_rejects_wrong_hash_and_keeps_nothing(tmp_path, field):
    data = tar_gz(MEMBERS)
    wrong = {"sha256": "0" * 64, "md5": "0" * 32, "bytes": len(data) + 5}[field]
    with serve({"a.tar.gz": data}) as server:
        dataset = _dataset(tmp_path, f"{server.base}/a.tar.gz", data, **{field: wrong})
        with pytest.raises(fetch.FetchError) as info:
            fetch.fetch_dataset(dataset, tmp_path / "cache", tmp_path)
    assert field.replace("bytes", "byte") in str(info.value).lower() or "size" in str(info.value)
    cache = tmp_path / "cache"
    leftover = [p for p in cache.rglob("*") if p.is_file()] if cache.exists() else []
    assert leftover == [], leftover
    with pytest.raises(fetch.FetchError, match="not fetched"):
        fetch.extracted_root(cache, "librispeech-test-clean")


def test_FR_0_4_02_fetch_resumes_partial_download(tmp_path):
    data = tar_gz(MEMBERS + [("pkg/keep/big.bin", bytes(range(256)) * 400)])
    with serve({"a.tar.gz": data}) as server:
        dataset = _dataset(tmp_path, f"{server.base}/a.tar.gz", data)
        server.cut_after["a.tar.gz"] = 1000          # the first transfer stops after 1000 bytes
        fetch.fetch_dataset(dataset, tmp_path / "cache", tmp_path)
        assert server.requests[0] == ("a.tar.gz", None)
        assert server.requests[1] == ("a.tar.gz", "bytes=1000-")
        assert server.sent["a.tar.gz"] == len(data)   # nothing was sent twice
    # a .part left by an earlier, interrupted command is resumed too
    cache2 = tmp_path / "cache2"
    part = cache2 / "downloads" / "librispeech-test-clean-a.tar.gz.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(data[:777])
    with serve({"a.tar.gz": data}) as server:
        dataset = _dataset(tmp_path, f"{server.base}/a.tar.gz", data)
        fetch.fetch_dataset(dataset, cache2, tmp_path)
        assert server.requests == [("a.tar.gz", "bytes=777-")]
    # a server that ignores Range sends everything again; the result is still exact
    cache3 = tmp_path / "cache3"
    part3 = cache3 / "downloads" / "librispeech-test-clean-a.tar.gz.part"
    part3.parent.mkdir(parents=True)
    part3.write_bytes(b"garbage")
    with serve({"a.tar.gz": data}) as server:
        server.honour_range = False
        dataset = _dataset(tmp_path, f"{server.base}/a.tar.gz", data)
        result = fetch.fetch_dataset(dataset, cache3, tmp_path)
    assert result.archive_path.read_bytes() == data


def test_FR_0_4_02_second_fetch_downloads_nothing(tmp_path):
    data = tar_gz(MEMBERS)
    with serve({"a.tar.gz": data}) as server:
        dataset = _dataset(tmp_path, f"{server.base}/a.tar.gz", data)
        first = fetch.fetch_dataset(dataset, tmp_path / "cache", tmp_path)
        before = {p: p.stat().st_mtime_ns for p in first.extracted_root.rglob("*") if p.is_file()}
        second = fetch.fetch_dataset(dataset, tmp_path / "cache", tmp_path)
        assert len(server.requests) == 1
    assert second.downloaded_bytes == 0 and not second.extracted
    assert {p: p.stat().st_mtime_ns for p in second.extracted_root.rglob("*") if p.is_file()} == before
    # a damaged extracted file is noticed and the extraction is redone from the kept archive, without a download
    (first.extracted_root / "pkg/keep/a.txt").write_bytes(b"changed")
    third = fetch.fetch_dataset(dataset, tmp_path / "cache", tmp_path)
    assert third.extracted and third.downloaded_bytes == 0
    assert (third.extracted_root / "pkg/keep/a.txt").read_bytes() == b"A" * 3000


def _info(name, kind=tarfile.REGTYPE, size=0, link=""):
    info = tarfile.TarInfo(name)
    info.type, info.size, info.linkname = kind, size, link
    return info


@pytest.mark.parametrize("bad", [
    (_info("/pkg/keep/abs.txt", size=1), b"x"),
    (_info("pkg/keep/../../escape.txt", size=1), b"x"),
    (_info("pkg/keep/link", tarfile.SYMTYPE, link="/etc/passwd"), None),
    (_info("pkg/keep/hard", tarfile.LNKTYPE, link="pkg/README"), None),
    (_info("pkg/keep/fifo", tarfile.FIFOTYPE), None),
])
def test_FR_0_4_02_extracts_only_listed_members_safely(tmp_path, bad):
    import gzip
    data = gzip.compress(_raw_tar([(_info("pkg/README", size=2), b"ok"), bad]), mtime=0)
    with serve({"a.tar.gz": data}) as server:
        dataset = _dataset(tmp_path, f"{server.base}/a.tar.gz", data, extract=["pkg/README", "pkg/keep/**", "**/escape.txt"])
        with pytest.raises(fetch.FetchError, match="unsafe|not a regular file"):
            fetch.fetch_dataset(dataset, tmp_path / "cache", tmp_path)
    assert not (tmp_path / "escape.txt").exists() and not (tmp_path.parent / "escape.txt").exists()
    assert not (tmp_path / "cache" / "librispeech-test-clean").exists()


def test_FR_0_4_02_members_outside_the_patterns_are_never_written(tmp_path):
    data = tar_gz(MEMBERS)
    with serve({"a.tar.gz": data}) as server:
        dataset = _dataset(tmp_path, f"{server.base}/a.tar.gz", data, extract=["pkg/keep/*.txt"])
        result = fetch.fetch_dataset(dataset, tmp_path / "cache", tmp_path)
    files = sorted(p.relative_to(result.extracted_root).as_posix() for p in result.extracted_root.rglob("*")
                   if p.is_file())
    assert files == [".aqis-complete.json", "pkg/keep/a.txt"]   # '*' stays within one folder
    with serve({"a.tar.gz": data}) as server:
        dataset = _dataset(tmp_path, f"{server.base}/a.tar.gz", data, extract=["pkg/keep/**", "pkg/missing/**"])
        with pytest.raises(fetch.FetchError, match="pkg/missing/\\*\\* matched no member"):
            fetch.fetch_dataset(dataset, tmp_path / "cache-b", tmp_path)


def test_FR_0_4_02_refuses_cache_not_ignored_by_git(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text("/ignored/\n", encoding="utf-8")
    data = tar_gz(MEMBERS)
    with serve({"a.tar.gz": data}) as server:
        dataset = _dataset(tmp_path, f"{server.base}/a.tar.gz", data)
        with pytest.raises(fetch.FetchError, match="not ignored by git"):
            fetch.fetch_dataset(dataset, repo / "visible", repo)
        assert server.requests == []
        fetch.fetch_dataset(dataset, repo / "ignored" / "cache", repo)
    assert subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True,
                          text=True).stdout.strip() == "?? .gitignore"


def test_FR_0_4_02_default_cache_is_ignored_by_git():
    out = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "data/raw/aqis_lab/x"])
    assert out.returncode == 0
    assert fetch.DEFAULT_CACHE == "data/raw/aqis_lab"


def _corpus_facts():
    """Facts of corpus-v1.tar.gz, recomputed here from the archive for the report in SMOKE_PACK.md."""
    with tarfile.open(ROOT / "corpus-v1.tar.gz", "r:gz") as tf:
        names = tf.getnames()
        manifest = json.load(tf.extractfile("corpus/manifest.json"))
        log = json.load(tf.extractfile("corpus/build/recipe_log.json"))
    wavs = [n for n in names if n.endswith(".wav")]
    categories = {}
    for name in wavs:
        stem = name.rsplit("/", 1)[1]
        cat = re.sub(r"_(dev|test)_.*$", "", stem)
        cat = re.sub(r"_(dev|test)$", "", cat)
        categories[cat] = categories.get(cat, 0) + 1
    fields = sorted({k for rec in manifest for k in rec})
    flac = {s for rec in log for s in rec["provenance_sources"] if s.endswith(".flac")}
    speakers = {s.split("-")[0] for s in flac}
    return len(names), len(wavs), categories, fields, len(flac), len(speakers)


def test_FR_0_4_02_corpus_report_matches_archive():
    members, n_wav, categories, fields, n_flac, n_speakers = _corpus_facts()
    text = (ROOT / "docs" / "data" / "SMOKE_PACK.md").read_text(encoding="utf-8")
    section = text.split("## What corpus-v1.tar.gz contains", 1)[1].split("\n## ", 1)[0]
    assert f"{members} members" in section and f"{n_wav} WAV clips" in section
    for cat, count in categories.items():
        assert re.search(rf"\| `{cat}` \| {count} \|", section), (cat, count)
    assert "transcript" not in fields
    assert "no transcripts" in section.lower()
    assert f"{n_flac} LibriSpeech FLAC" in section and f"{n_speakers} speakers" in section
    assert "not usable" in section.lower()


def test_FR_0_4_02_no_raw_corpus_committed():
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "data"], capture_output=True, text=True,
                           check=True).stdout.split()
    assert not [f for f in files if f.startswith("data/raw/")]
    audio_like = [f for f in files if re.search(r"\.(wav|flac|mp3|ogg|opus|tar|gz|tgz|zip)$", f)]
    allowed = re.compile(r"^data/(tts_smoke/[0-9]{2}\.wav|packs/[a-z0-9-]+/v[0-9]+/[a-z0-9.-]+\.tar)$")
    assert [f for f in audio_like if not allowed.match(f)] == []


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_4_02_dataset_pins_match_openslr(tmp_path_factory):
    """Fetch the three real archives (about 11.8 GB) into the default cache and check the pins."""
    loaded = ds.load_datasets(ROOT / "data" / "registry" / "datasets.yaml")
    cache = ROOT / fetch.DEFAULT_CACHE
    for dataset_id in ("librispeech-test-clean", "librispeech-test-other", "musan"):
        dataset = loaded.datasets[dataset_id]
        assert dataset["url"].startswith("https://www.openslr.org/resources/")
        result = fetch.fetch_dataset(dataset, cache, ROOT)
        digest = hashlib.sha256()
        with open(result.archive_path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
        assert digest.hexdigest() == dataset["sha256"]

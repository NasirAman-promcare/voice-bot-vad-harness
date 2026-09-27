"""Pack archives: normalised uncompressed tar shards with exact sizes, member paths and the Drive-friendly limits.

CAPABILITIES:
  CAP-PACK-004: the hard limits MAX_FILES_PER_FOLDER (1,000 entries in any folder) and MAX_ARCHIVE_BYTES (200,000,000 bytes per tar file); member_paths() places a category's clips at <category>/<clip_id>.wav, or in numbered subfolders of at most the folder limit when a category has more clips; tar_size() gives a tar file's exact size before it is written; plan_shards() splits a category's members into shards below the byte limit and rejects a clip that cannot fit in one; tar_bytes() writes a USTAR tar whose every header is normalised (regular file, mode 0644, uid and gid 0, no user or group names, one fixed mtime), in the given order; folder_entry_counts() counts the entries of every folder a list of paths creates [tests: test_FR_0_4_05_tar_headers_are_normalised, test_FR_0_4_05_members_in_documented_order, test_FR_0_4_06_splits_archives_at_size_limit, test_FR_0_4_06_splits_member_folders_at_1000_files, test_FR_0_4_06_rejects_clip_larger_than_archive_limit, test_FR_0_4_06_tar_size_is_exact]
INPUTS AND OUTPUTS: (member path, bytes) pairs and limits in; tar bytes, shard plans and counts out; ArchiveError.
CONTRACTS: pack layout (docs/data/SMOKE_PACK.md, "Layout").
INVARIANTS:
  - The same members and mtime give the same bytes; no header depends on the machine, the user or the clock.
  - tar_size() equals the length of tar_bytes() for the same members.
NOT IN SCOPE:
  - What goes into the archives (aqis_lab/packs/build.py); checking built archives (aqis_lab/packs/verify.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-05, FR-0.4-06 created.
"""
import io
import tarfile

MAX_FILES_PER_FOLDER = 1000
MAX_ARCHIVE_BYTES = 200_000_000
BLOCK = tarfile.BLOCKSIZE
RECORD = tarfile.RECORDSIZE
MAX_NAME_BYTES = 100


class ArchiveError(ValueError):
    """Members cannot be laid out or archived within the pack's rules."""


def member_size(n_bytes):
    """Bytes a regular member of n_bytes takes in a USTAR tar: one header block and its data padded to blocks."""
    return BLOCK + -(-n_bytes // BLOCK) * BLOCK


def tar_size(sizes):
    """Exact size of a tar file holding members of these sizes: members, two end blocks, padding to a record."""
    raw = sum(member_size(n) for n in sizes) + 2 * BLOCK
    return -(-raw // RECORD) * RECORD


def member_paths(category, clip_ids, max_files):
    """Member path of each clip of a category, in the order given; numbered subfolders when above max_files."""
    if len(clip_ids) <= max_files:
        return [f"{category}/{clip_id}.wav" for clip_id in clip_ids]
    folders = -(-len(clip_ids) // max_files)
    if folders > max_files:
        raise ArchiveError(f"category {category} has {len(clip_ids)} clips; more than {max_files} folders of "
                           f"{max_files} would be needed")
    return [f"{category}/{i // max_files:03d}/{clip_id}.wav" for i, clip_id in enumerate(clip_ids)]


def folder_entry_counts(paths):
    """{folder: number of entries (files and subfolders)} for the folders these relative file paths create."""
    entries = {}
    for path in paths:
        parts = path.split("/")
        for depth in range(len(parts)):
            folder = "/".join(parts[:depth])
            entries.setdefault(folder, set()).add(parts[depth])
    return {folder: len(names) for folder, names in entries.items()}


def plan_shards(members, max_bytes):
    """Split [(path, size)] in order into shards whose tar size stays within max_bytes; returns lists of indexes."""
    shards, current = [], []
    for index, (path, size) in enumerate(members):
        if tar_size([size]) > max_bytes:
            raise ArchiveError(f"{path} ({size} bytes) does not fit in one archive of at most {max_bytes} bytes")
        if current and tar_size([members[i][1] for i in current] + [size]) > max_bytes:
            shards.append(current)
            current = []
        current.append(index)
    if current:
        shards.append(current)
    return shards


def tar_bytes(members, mtime):
    """USTAR tar bytes of [(path, data)] in the given order, every header normalised."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for path, data in members:
            encoded = path.encode("ascii", errors="strict") if path.isascii() else None
            if encoded is None or len(encoded) > MAX_NAME_BYTES:
                raise ArchiveError(f"member path {path!r} must be ASCII and at most {MAX_NAME_BYTES} bytes")
            info = tarfile.TarInfo(path)
            info.size = len(data)
            info.mtime = mtime
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.type = tarfile.REGTYPE
            tf.addfile(info, io.BytesIO(data))
    data = buf.getvalue()
    expected = tar_size([len(d) for _, d in members])
    if len(data) != expected:
        raise ArchiveError(f"tar writer produced {len(data)} bytes, the layout rule gives {expected}")
    return data


def archive_name(manifest_id, version, category, index):
    return f"{manifest_id}-{version}-{category}-{index:03d}.tar"

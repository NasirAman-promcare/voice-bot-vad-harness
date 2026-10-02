"""Shard plans: split a run's clips into shards of at most N minutes of expected work (default 30) or N clips.

CAPABILITIES:
  CAP-RUN-005: plan_shards() packs clips greedily in manifest order and closes a shard before adding a clip would pass the expected-work limit (clip duration x the task's seconds per audio second) or the clip limit; a clip over the limit gets a shard of its own; build_plan() takes an optional clip subset (manifest order, recorded as clip_selection; WP-0.7) and records the limits, the task and each shard's clip IDs and expected work, with plan_id = SHA-256 of the canonical plan [tests: test_FR_0_5_05_default_shard_is_at_most_30_minutes_of_expected_work, test_FR_0_5_05_shard_size_is_configurable, test_FR_0_7_07_clip_subset_goes_into_the_plan_not_the_card]
INPUTS AND OUTPUTS: clip durations and limits in; lists of clip indexes and a plan dict out.
CONTRACTS: shard plan format in docs/runner/RUNNER.md.
INVARIANTS:
  - The plan depends only on the manifest, the task, the limits and the clip subset: the same inputs give the same
    plan_id anywhere.
NOT IN SCOPE:
  - Running shards (aqis_lab/runner/run.py).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-05 created.
  2026-09-30 WP-0.7 FR-0.7-07: build_plan takes an optional clip subset; a plan without one is unchanged.
"""
from aqis_lab.contracts.canonical import sha256_canonical

PLAN_VERSION = "1.0"
DEFAULT_SHARD_MINUTES = 30


class PlanError(ValueError):
    """The shard limits are not usable."""


def plan_shards(durations, seconds_per_audio_second, shard_minutes=DEFAULT_SHARD_MINUTES, shard_clips=None):
    """Lists of clip indexes, one per shard."""
    if not shard_minutes > 0:
        raise PlanError(f"--shard-minutes must be greater than 0, got {shard_minutes}")
    if shard_clips is not None and shard_clips < 1:
        raise PlanError(f"--shard-clips must be at least 1, got {shard_clips}")
    limit, shards, current, work = shard_minutes * 60, [], [], 0.0
    for index, duration in enumerate(durations):
        cost = duration * seconds_per_audio_second
        if current and (work + cost > limit or (shard_clips is not None and len(current) >= shard_clips)):
            shards.append(current)
            current, work = [], 0.0
        current.append(index)
        work += cost
    if current:
        shards.append(current)
    return shards


def build_plan(run_card_id, task, manifest, shard_minutes=DEFAULT_SHARD_MINUTES, shard_clips=None, clip_ids=None):
    """The shard plan; `clip_ids` limits the run to those clips (manifest order) and is recorded in the plan."""
    clips = manifest["clips"] if clip_ids is None else [c for c in manifest["clips"] if c["clip_id"] in set(clip_ids)]
    ratio = task.seconds_per_audio_second
    shards = plan_shards([c["duration_s"] for c in clips], ratio, shard_minutes, shard_clips)
    plan = {
        "plan_version": PLAN_VERSION,
        "run_card_id": run_card_id,
        "task": {"name": task.name, "version": task.version, "seconds_per_audio_second": ratio},
        "shard_minutes": shard_minutes,
        "shard_clips": shard_clips,
        "shards": [{"index": i, "clip_ids": [clips[j]["clip_id"] for j in shard],
                    "expected_work_s": sum(clips[j]["duration_s"] * ratio for j in shard)}
                   for i, shard in enumerate(shards)],
    }
    if clip_ids is not None:
        plan["clip_selection"] = {"clip_ids": [c["clip_id"] for c in clips]}
    plan["plan_id"] = sha256_canonical(plan)
    return plan


def oversize_shards(plan):
    """Indexes of single-clip shards whose expected work passes the minute limit."""
    limit = plan["shard_minutes"] * 60
    return [s["index"] for s in plan["shards"] if s["expected_work_s"] > limit]

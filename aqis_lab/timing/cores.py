"""Core reservation on Oracle: pin timing runs to the reserved cores in oracle.yaml and batch runs to the others.

CAPABILITIES:
  CAP-CORES-001: mode_group() puts every run-card mode in exactly one group: batch (batch) or timing (realspeed_cpu, gpu_compute_delay, tier2_live, nearlive_replay, human_session; owner decision, question 8); build_plan() reads cores.reserved_for_timing and refuses a reserved CPU that is not online, a plan leaving no batch CPU, or a reservation that splits a physical core (owner decision, question 10) [tests: test_FR_0_6_04_every_mode_is_timing_or_batch, test_FR_0_6_04_plan_reserves_config_cores_and_batches_the_rest, test_FR_0_6_04_reservation_must_leave_a_batch_core, test_FR_0_6_04_reserved_core_must_be_online, test_FR_0_6_04_reservation_must_not_split_a_physical_core, test_FR_0_6_04_missing_topology_is_an_error, test_FR_0_6_04_committed_reservation_fits_oracle_probe]
  CAP-CORES-002: pin_for_mode() on the oracle platform pins every thread of the process (not only the calling one) to the mode's CPUs, reads each back and raises CoreError on any refusal or difference; on other platforms it pins nothing and says so (owner decision, question 9) [tests: test_FR_0_6_04_timing_process_pinned_to_reserved_cores, test_FR_0_6_04_batch_run_kept_off_reserved_cores, test_FR_0_6_04_no_pinning_off_oracle, test_FR_0_6_04_pin_failure_is_an_error, test_FR_0_6_04_real_oracle_pinning]
INPUTS AND OUTPUTS: a run mode, a SystemView and the oracle.yaml path in; a Pinning (what was done, for logs) out;
  CoreError (or OracleConfigError, PlatformError) on failure.
CONTRACTS: run-card v1 `mode` enum; config/aqis_lab/oracle.yaml `cores.reserved_for_timing`.
INVARIANTS:
  - Machine facts (online CPUs, siblings, threads, affinity) come from aqis_lab.platform; this module only sets
    affinity.
  - A pin that did not take is an error, never a warning; child processes inherit the pin.
NOT IN SCOPE:
  - Keeping programs outside the lab off the reserved cores (optional system setting, docs/oracle/ORACLE_RUNBOOK.md).
CHANGE LOG:
  2026-09-28 WP-0.6 FR-0.6-04 created.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from aqis_lab import oracle_config
from aqis_lab import platform as lp

BATCH_MODES = ("batch",)
TIMING_MODES = ("realspeed_cpu", "gpu_compute_delay", "tier2_live", "nearlive_replay", "human_session")
RESERVING_PLATFORM = "oracle"
MAX_PASSES = 50


class CoreError(RuntimeError):
    """The core reservation is not possible on this machine, or a pin did not take."""


@dataclass(frozen=True)
class CorePlan:
    reserved: frozenset
    batch: frozenset
    config: Path


@dataclass(frozen=True)
class Pinning:
    mode: str
    group: str                  # "timing" or "batch"
    platform: str
    cpus: frozenset | None      # None: nothing pinned (no reservation on this platform)
    plan: CorePlan | None

    def describe(self):
        if self.plan is None:
            return f"no reservation (platform {self.platform})"
        if self.group == "timing":
            return (f"timing on {format_cpus(self.plan.reserved)} (batch on {format_cpus(self.plan.batch)}; "
                    f"config {self.plan.config})")
        return (f"batch on {format_cpus(self.plan.batch)} (timing reserved {format_cpus(self.plan.reserved)}; "
                f"config {self.plan.config})")


def format_cpus(cpus):
    """Kernel CPU-list text ("0-1,3") for a set of CPU numbers."""
    cpus = sorted(cpus)
    parts, i = [], 0
    while i < len(cpus):
        j = i
        while j + 1 < len(cpus) and cpus[j + 1] == cpus[j] + 1:
            j += 1
        parts.append(str(cpus[i]) if i == j else f"{cpus[i]}-{cpus[j]}")
        i = j + 1
    return ",".join(parts)


def mode_group(mode):
    """'timing' or 'batch' for a run-card mode; CoreError for an unknown mode."""
    if mode in BATCH_MODES:
        return "batch"
    if mode in TIMING_MODES:
        return "timing"
    raise CoreError(f"unknown run mode {mode!r}; known modes: {', '.join(BATCH_MODES + TIMING_MODES)}")


def build_plan(system=None, config=None):
    """The CorePlan for this machine from oracle.yaml: reserved CPUs for timing, every other online CPU for batch."""
    system = system or lp.SystemView.real()
    cfg = oracle_config.load(config)
    reserved = frozenset(cfg.reserved_for_timing)
    online = lp.online_cpus(system)
    missing = reserved - online
    if missing:
        raise CoreError(f"core reservation is not possible on this machine: reserved CPU(s) {format_cpus(missing)} "
                        f"are not online (online CPUs {format_cpus(online)}; {cfg.path}, cores.reserved_for_timing)")
    batch = online - reserved
    if not batch:
        raise CoreError(f"core reservation is not possible on this machine: reserving {format_cpus(reserved)} "
                        f"leaves no CPU left for batch runs (online CPUs {format_cpus(online)}; {cfg.path})")
    for cpu in sorted(reserved):
        outside = lp.core_siblings(cpu, system) - reserved
        if outside:
            raise CoreError(f"core reservation splits a physical core: CPU {cpu} shares a physical core with CPU "
                            f"{format_cpus(outside)}, which is not reserved; reserve whole cores ({cfg.path}, "
                            f"cores.reserved_for_timing)")
    return CorePlan(reserved=reserved, batch=batch, config=cfg.path)


def pin_process(cpus):
    """Pin every thread of this process to `cpus`, then read every thread back; CoreError on any failure."""
    cpus = frozenset(cpus)
    done = set()
    for _ in range(MAX_PASSES):
        new = [tid for tid in lp.thread_ids() if tid not in done]
        if not new:
            break
        for tid in new:
            try:
                os.sched_setaffinity(tid, cpus)
            except ProcessLookupError:
                done.add(tid)       # the thread ended after it was listed; nothing is left to pin
                continue
            except OSError as exc:
                raise CoreError(f"cannot pin thread {tid} to CPUs {format_cpus(cpus)}: {exc.strerror or exc}") from exc
            done.add(tid)
    else:
        raise CoreError(f"new threads kept appearing while pinning to CPUs {format_cpus(cpus)} ({MAX_PASSES} passes)")
    for tid in lp.thread_ids():
        try:
            got = lp.thread_affinity(tid)
        except ProcessLookupError:
            continue                # ended after the listing; it no longer runs anywhere
        if got != cpus:
            raise CoreError(f"thread {tid} runs on CPUs {format_cpus(got)} after pinning, not {format_cpus(cpus)}")


def pin_for_mode(mode, system=None, config=None):
    """Pin this process for a run of `mode` (timing: reserved CPUs, batch: the others) on the oracle platform."""
    group = mode_group(mode)
    system = system or lp.SystemView.real()
    platform = lp.detect_platform(system).platform
    if platform != RESERVING_PLATFORM:
        return Pinning(mode=mode, group=group, platform=platform, cpus=None, plan=None)
    plan = build_plan(system, config)
    cpus = plan.reserved if group == "timing" else plan.batch
    pin_process(cpus)
    return Pinning(mode=mode, group=group, platform=platform, cpus=cpus, plan=plan)

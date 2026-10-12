"""Model router, stats collector, and client factory.

CAPABILITIES:
  CAP-OUTSOURCING-ROUTER: Choose model based on risk tier, token limits, governor delays, and first-pass performance stats.
    [tests: test_model_stats_empty_and_unreadable, test_router_pinned_model_valid,
    test_router_pinned_model_not_eligible, test_router_default_size_ruled_out, test_client_for_factory,
    test_FR_1_0_02_mc01_mc08_mc11_accepted_run_end_to_end,
    test_FR_1_0_02_mc02_t1_order_never_goes_to_a_model_without_t1,
    test_FR_1_0_02_mc02_pinned_model_without_the_tier_exits_2,
    test_FR_1_0_02_mc02_router_skips_models_without_the_tier,
    test_FR_1_0_02_mc03_daily_quota_switches_without_using_an_attempt,
    test_FR_1_0_02_mc03_pool_exhausted_pauses_then_resumes_at_the_same_part,
    test_FR_1_0_02_mc04_low_first_pass_model_is_chosen_after_all_others,
    test_FR_1_0_02_mc05_credential_error_moves_to_other_provider_with_access_line,
    test_FR_1_0_02_mc05_no_provider_left_exits_7, test_FR_1_0_02_mc06_questions_exit_4_keeps_earlier_parts,
    test_FR_1_0_02_mc07_read_only_test_changed_exits_9_and_commits_nothing,
    test_FR_1_0_02_mc09_cut_off_two_file_part_is_split_per_file, test_FR_1_0_02_mc09_cut_off_one_file_part_exits_5,
    test_FR_1_0_02_mc10_rerun_after_failed_attempt_discards_and_continues,
    test_FR_1_0_02_mc10_step_log_of_another_wp_branch_exits_2_before_any_merge,
    test_FR_1_0_14_mc12_models_reports_a_missing_model_and_exits_2, test_FR_1_0_14_models_all_present_exits_0,
    test_FR_1_0_14_mc13_too_large_for_one_model_goes_to_one_that_fits, test_FR_1_0_14_mc13_no_model_fits_exits_13,
    test_FR_1_0_02_dry_run_measures_and_sends_nothing, test_FR_1_0_14_status_reports_resets_and_sends_nothing]
INPUTS AND OUTPUTS: Accepts work order, input token estimate, and exclusions; returns ModelSpec or builds client.
CONTRACTS: none.
INVARIANTS:
  - Pinned models are strictly enforced.
  - Demoted models move behind all other candidate models.
NOT IN SCOPE:
  - Direct HTTP calls (delegated to clients).
CHANGE LOG:
  2026-10-10 WO-1.0-11 created.
  2026-10-10 WO-1.0-11 FIX 1: split _choose_default to follow shape rules.
  2026-10-10 WP-1.0 FR-1.0-02 review fix (Claude): "size alone" only when every model left fails on size; the message
    names each model's limit (B9).
  2026-10-12 WP-1.0 FR-1.0-03 (Claude): [tests: …] names test functions, not files (gate E3, Lab Map).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from tools.outsourcing.gemini_client import GeminiClient
from tools.outsourcing.governor import Governor
from tools.outsourcing.limits import LimitsError, ModelSpec, Pool, effective
from tools.outsourcing.openai_client import OpenAIClient
from tools.outsourcing.steplog import StepLogError, parse
from tools.outsourcing.workorder import WorkOrder

__all__ = [
    "NoEligibleModel",
    "PoolExhausted",
    "PerModelStat",
    "ModelStats",
    "model_stats",
    "Router",
    "client_for",
]


class NoEligibleModel(Exception):
    """Raised when no model qualifies for the given work order or request."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PoolExhausted(Exception):
    """Raised when all qualifying models are daily/monthly exhausted."""

    def __init__(self, earliest_reset: datetime | None = None) -> None:
        msg = f"Pool exhausted; earliest reset at {earliest_reset}" if earliest_reset else "Pool exhausted"
        super().__init__(msg)
        self.earliest_reset = earliest_reset


@dataclass
class PerModelStat:
    parts: int = 0
    first_pass_parts: int = 0
    attempts: int = 0

    @property
    def first_pass_rate(self) -> float:
        return self.first_pass_parts / self.parts if self.parts > 0 else 0.0


@dataclass
class ModelStats:
    models: dict[str, PerModelStat] = field(default_factory=dict)
    unreadable: tuple[str, ...] = ()


def model_stats(root: str | Path) -> ModelStats:
    root_path = Path(root)
    returns_dir = root_path / "docs" / "outsourcing" / "returns"
    stats = ModelStats()

    if not returns_dir.exists():
        return stats

    unreadable_list: list[str] = []
    models_dict: dict[str, PerModelStat] = {}

    for steps_file in sorted(returns_dir.glob("*/steps.md")):
        rel_path = str(steps_file.relative_to(root_path))
        try:
            text = steps_file.read_text(encoding="utf-8")
            log = parse(text)
            for acc in log.accepted:
                p_stat = models_dict.setdefault(acc.model, PerModelStat())
                p_stat.parts += 1
                p_stat.attempts += acc.attempts
                if acc.attempts == 1:
                    p_stat.first_pass_parts += 1
        except (StepLogError, OSError):
            unreadable_list.append(rel_path)

    stats.models = models_dict
    stats.unreadable = tuple(unreadable_list)
    return stats


class Router:

    def __init__(self, pool: Pool, governor: Governor, stats: ModelStats) -> None:
        self.pool = pool
        self.governor = governor
        self.stats = stats

    def choose(
        self,
        order: WorkOrder,
        input_estimate: int,
        exclude: set[str] | tuple[str, ...] | list[str] | None = None,
    ) -> ModelSpec:
        excl = set(exclude or ())

        if order.model != "default":
            return self._choose_pinned(order, input_estimate, excl)

        return self._choose_default(order, input_estimate, excl)

    def _choose_pinned(self, order: WorkOrder, input_estimate: int, exclude: set[str]) -> ModelSpec:
        try:
            spec = self.pool.model(order.model)
        except LimitsError as exc:
            raise NoEligibleModel(f"Pinned model '{order.model}' not available in pool: {exc}") from exc

        if not spec.provider.enabled:
            raise NoEligibleModel(f"Provider '{spec.provider.name}' for pinned model '{order.model}' is disabled")

        if order.risk_tier not in spec.risk_tiers:
            raise NoEligibleModel(f"Pinned model '{order.model}' does not support risk tier '{order.risk_tier}'")

        if spec.name in exclude:
            raise NoEligibleModel(f"Pinned model '{order.model}' is excluded")

        ms = self.governor.model_stats.get(spec.name)
        adaptive = ms.adaptive_factor if ms else 1.0
        learned = ms.learned_limits if ms else {}
        eff = effective(self.pool, spec, adaptive, learned)

        if spec.max_input_tokens < input_estimate or eff.input_token_ceiling < input_estimate:
            raise NoEligibleModel(
                f"Pinned model '{order.model}' cannot fit size {input_estimate} "
                f"(max {spec.max_input_tokens}, ceiling {eff.input_token_ceiling})"
            )

        reset_dt = self.governor.exhausted_until(spec.name)
        if reset_dt is not None:
            raise PoolExhausted(earliest_reset=reset_dt)

        return spec

    def _choose_default(self, order: WorkOrder, input_estimate: int, exclude: set[str]) -> ModelSpec:
        all_candidates = self.pool.candidates(order.risk_tier)
        if not all_candidates:
            raise NoEligibleModel(f"No enabled model in pool supports risk tier '{order.risk_tier}'")

        qualifying, too_small = self._filter_qualifying(all_candidates, input_estimate, exclude)

        if not qualifying:
            if too_small:
                limits_text = ", ".join(f"{name} fits {limit}" for name, limit in too_small.items())
                raise NoEligibleModel(
                    f"Size alone ({input_estimate} tokens) ruled out every model left for risk tier "
                    f"'{order.risk_tier}': {limits_text}"
                )
            raise NoEligibleModel(f"No eligible model available for risk tier '{order.risk_tier}'")

        unexhausted = self._filter_unexhausted(qualifying)
        ordered = self._rank_candidates(unexhausted, order.risk_tier)

        for m in ordered:
            if self.governor.delay_for(m.name, input_estimate) == 0.0:
                return m

        return ordered[0]

    def _filter_qualifying(
        self, candidates: list[ModelSpec], input_estimate: int, exclude: set[str]
    ) -> tuple[list[ModelSpec], dict[str, int]]:
        """Models that fit the request, and, for each model left out only by size, the input it can take."""
        qualifying: list[ModelSpec] = []
        too_small: dict[str, int] = {}

        for m in candidates:
            if m.name in exclude:
                continue
            ms = self.governor.model_stats.get(m.name)
            adaptive = ms.adaptive_factor if ms else 1.0
            learned = ms.learned_limits if ms else {}
            eff = effective(self.pool, m, adaptive, learned)
            fits = min(m.max_input_tokens, eff.input_token_ceiling)

            if fits >= input_estimate:
                qualifying.append(m)
            else:
                too_small[m.name] = fits

        return qualifying, too_small

    def _filter_unexhausted(self, qualifying: list[ModelSpec]) -> list[ModelSpec]:
        unexhausted: list[ModelSpec] = []
        resets: list[datetime] = []

        for m in qualifying:
            reset_dt = self.governor.exhausted_until(m.name)
            if reset_dt is not None:
                resets.append(reset_dt)
            else:
                unexhausted.append(m)

        if not unexhausted:
            earliest = min(resets) if resets else None
            raise PoolExhausted(earliest_reset=earliest)

        return unexhausted

    def _rank_candidates(self, candidates: list[ModelSpec], risk_tier: str) -> list[ModelSpec]:
        best_rate = -1.0
        for m in self.pool.candidates(risk_tier):
            st = self.stats.models.get(m.name)
            if st and st.parts >= 8:
                if st.first_pass_rate > best_rate:
                    best_rate = st.first_pass_rate

        if best_rate < 0.0:
            return list(candidates)

        normal: list[ModelSpec] = []
        demoted: list[ModelSpec] = []

        for m in candidates:
            st = self.stats.models.get(m.name)
            if st and st.parts >= 8 and (best_rate - st.first_pass_rate) >= 0.25:
                demoted.append(m)
            else:
                normal.append(m)

        return normal + demoted


def client_for(spec: ModelSpec, governor: Governor, timeout: float = 300.0, base_url_override: str | None = None):
    if spec.provider.api == "gemini":
        return GeminiClient(spec, governor, timeout=timeout, base_url=base_url_override)
    return OpenAIClient(spec, governor, timeout=timeout, base_url=base_url_override)

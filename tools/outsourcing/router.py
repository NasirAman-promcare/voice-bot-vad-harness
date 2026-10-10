"""Model router, stats collector, and client factory.

CAPABILITIES:
  CAP-OUTSOURCING-ROUTER: Choose model based on risk tier, token limits, governor delays, and first-pass performance stats. [tests: test_router.py, test_acceptance_wo_1_0_11.py]
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

        qualifying, size_ruled_out = self._filter_qualifying(all_candidates, input_estimate, exclude)

        if not qualifying:
            if size_ruled_out:
                raise NoEligibleModel(
                    f"Size alone ({input_estimate} tokens) ruled out all candidate models for risk tier '{order.risk_tier}'"
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
    ) -> tuple[list[ModelSpec], bool]:
        qualifying: list[ModelSpec] = []
        size_ruled_out = True

        for m in candidates:
            if m.name in exclude:
                continue
            ms = self.governor.model_stats.get(m.name)
            adaptive = ms.adaptive_factor if ms else 1.0
            learned = ms.learned_limits if ms else {}
            eff = effective(self.pool, m, adaptive, learned)

            if m.max_input_tokens >= input_estimate and eff.input_token_ceiling >= input_estimate:
                qualifying.append(m)
                size_ruled_out = False

        return qualifying, size_ruled_out

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

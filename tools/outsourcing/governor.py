"""Sliding-window pacing, adaptive rate limits, persisted state, and reporting.

CAPABILITIES:
  CAP-OUTSOURCING-GOVERNOR: Pacing, adaptive factor, state persistence, and report generation. [tests: test_governor, test_acceptance_wo_1_0_10]
INPUTS AND OUTPUTS:
  Paces request slots, updates counts and learned limits, persists state, generates GovernorReport.
CONTRACTS: none.
INVARIANTS:
  - State file updates use file locking for safe process sharing.
NOT IN SCOPE:
  - Network transport execution.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
  2026-10-10 WP-1.0 FR-1.0-14 FIX-2 (Claude): records, state file and lock moved to governor_state.py (400-line
    limit); wait_for_provider sleeps outside the lock.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from tools.outsourcing.limits import (
    EffectiveLimits, ModelSpec, Pool, ProviderSpec, _la_offset, _resolve_tz, effective, monthly_reset, next_reset,
)
from tools.outsourcing.governor_state import (
    FileLock, GovernorReport, ModelReport, ModelStats, ProviderReport, ProviderStats, load_stats, save_stats,
)
from tools.outsourcing.quota import QuotaVerdict

__all__ = ["Governor", "GovernorReport", "ModelReport", "ProviderReport", "ModelStats", "ProviderStats"]


class Governor:

    def __init__(
        self,
        pool: Pool,
        state_path: Path | str,
        clock: Callable[[], float],
        sleeper: Callable[[float], None],
        rng: random.Random | None = None,
    ) -> None:
        self.pool = pool
        self.state_path = Path(state_path)
        self.clock = clock
        self.sleeper = sleeper
        self.rng = rng or random.Random()
        self.corrupt_state = False
        self.model_stats = {m: ModelStats() for m in pool.models()}
        self.provider_stats = {p: ProviderStats() for p in pool.providers()}
        with self._lock():
            self._load_state_unlocked()

    def _lock(self) -> FileLock:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        return FileLock(self.state_path.parent / f"{self.state_path.name}.lock")

    def _load_state_unlocked(self) -> None:
        if load_stats(self.state_path, self.model_stats, self.provider_stats, self.clock()):
            self._clean_old_counts()
            return
        self.corrupt_state = True  # E3: start fresh at 0.75, noted in the report
        for ms in self.model_stats.values():
            ms.adaptive_factor = 0.75

    def _save_state_unlocked(self) -> None:
        save_stats(self.state_path, self.model_stats, self.provider_stats)

    def _get_local_now(self, provider: ProviderSpec) -> datetime:
        now_dt = datetime.fromtimestamp(self.clock(), tz=timezone.utc)
        prov_tz, _ = _resolve_tz(provider.day_reset)
        if prov_tz is None and provider.day_reset == "America/Los_Angeles":
            return now_dt.astimezone(timezone(_la_offset(now_dt)))
        return now_dt.astimezone(prov_tz)

    def _current_date_str(self, provider: ProviderSpec) -> str:
        return self._get_local_now(provider).strftime("%Y-%m-%d")

    def _current_month_str(self, provider: ProviderSpec) -> str:
        return self._get_local_now(provider).strftime("%Y-%m")

    def _clean_old_counts(self) -> None:
        for m_spec in self.pool.models().values():
            today = self._current_date_str(m_spec.provider)
            self.model_stats[m_spec.name].daily_counts = {
                k: v for k, v in self.model_stats[m_spec.name].daily_counts.items() if k == today
            }
        for p_spec in self.pool.providers().values():
            ps = self.provider_stats[p_spec.name]
            today = self._current_date_str(p_spec)
            month = self._current_month_str(p_spec)
            ps.daily_counts = {k: v for k, v in ps.daily_counts.items() if k == today}
            ps.monthly_tokens = {k: v for k, v in ps.monthly_tokens.items() if k == month}

    def _clean_starts(self, now: float) -> None:
        for ms in self.model_stats.values():
            ms.starts = [(t, tok) for t, tok in ms.starts if now - t < 60.0]
        for ps in self.provider_stats.values():
            ps.starts = [(t, tok) for t, tok in ps.starts if now - t < 60.0]

    def _record_learned_limit_unlocked(self, model_name: str, key: str, value: int, scope: str = "model") -> None:
        m_spec = self.pool.model(model_name)
        ps = self.provider_stats[m_spec.provider.name]
        ms = self.model_stats[model_name]
        is_prov_scope = scope == "provider" or (getattr(m_spec, key, None) is None and getattr(m_spec.provider, key, None) is not None)
        target = ps if is_prov_scope else ms
        cfg = getattr(m_spec.provider, key, None) if is_prov_scope else getattr(m_spec, key, None)
        if cfg is None or value < cfg:
            target.learned_limits[key] = min(target.learned_limits.get(key, value), value)

    def record_learned_limit(self, model_name: str, key: str, value: int, scope: str = "model") -> None:
        with self._lock():
            self._load_state_unlocked()
            self._record_learned_limit_unlocked(model_name, key, value, scope)
            self._save_state_unlocked()

    def _check_model_delays(self, ms: ModelStats, eff: EffectiveLimits, now: float, input_tokens: int) -> list[float]:
        delays = [0.0]
        if ms.cooldown_until > now:
            delays.append(ms.cooldown_until - now)
        if eff.rpm is not None:
            mr = [t for t, _ in ms.starts if now - t < 60.0]
            if len(mr) >= eff.rpm:
                delays.append(mr[len(mr) - eff.rpm] + 60.0 - now)
        if eff.model_spacing > 0 and ms.starts:
            delays.append(ms.starts[-1][0] + eff.model_spacing - now)
        if eff.tpm_input is not None:
            mrt = sum(tok for t, tok in ms.starts if now - t < 60.0)
            if ms.starts and (mrt + input_tokens > eff.tpm_input):
                accum = mrt + input_tokens
                for t, tok in ms.starts:
                    accum -= tok
                    delays.append(t + 60.0 - now)
                    if accum <= eff.tpm_input:
                        break
        return delays

    def _check_provider_delays(
        self, ps: ProviderStats, m_spec: ModelSpec, eff: EffectiveLimits, now: float, input_tokens: int
    ) -> list[float]:
        delays = [0.0]
        if ps.cooldown_until > now:
            delays.append(ps.cooldown_until - now)
        p_cfg_rpm = ps.learned_limits.get("rpm", m_spec.provider.rpm)
        if p_cfg_rpm is not None:
            p_eff_rpm = max(1, math.floor(p_cfg_rpm * self.pool.safety * self.model_stats[m_spec.name].adaptive_factor / self.pool.share))
            pr = [t for t, _ in ps.starts if now - t < 60.0]
            if len(pr) >= p_eff_rpm:
                delays.append(pr[len(pr) - p_eff_rpm] + 60.0 - now)
        p_cfg_tpm = ps.learned_limits.get("tpm_input", m_spec.provider.tpm_input)
        if p_cfg_tpm is not None:
            p_eff_tpm = max(1, math.floor(p_cfg_tpm * self.pool.safety * self.model_stats[m_spec.name].adaptive_factor / self.pool.share))
            prt = sum(tok for t, tok in ps.starts if now - t < 60.0)
            if ps.starts and (prt + input_tokens > p_eff_tpm):
                accum = prt + input_tokens
                for t, tok in ps.starts:
                    accum -= tok
                    delays.append(t + 60.0 - now)
                    if accum <= p_eff_tpm:
                        break
        if eff.rps_spacing > 0 and ps.starts:
            delays.append(ps.starts[-1][0] + eff.rps_spacing - now)
        return delays

    def _delay_for_unlocked(self, model_name: str, input_tokens: int) -> float:
        now = self.clock()
        self._clean_starts(now)
        m_spec = self.pool.model(model_name)
        ms = self.model_stats[model_name]
        ps = self.provider_stats[m_spec.provider.name]
        eff = effective(self.pool, m_spec, ms.adaptive_factor, ms.learned_limits)
        m_delays = self._check_model_delays(ms, eff, now, input_tokens)
        p_delays = self._check_provider_delays(ps, m_spec, eff, now, input_tokens)
        return max(0.0, max(m_delays + p_delays))

    def delay_for(self, model_name: str, input_tokens: int) -> float:
        with self._lock():
            self._load_state_unlocked()
            return self._delay_for_unlocked(model_name, input_tokens)

    def wait_for_slot(self, model_name: str, input_tokens: int) -> float:
        waited = 0.0
        while True:
            with self._lock():
                self._load_state_unlocked()
                delay = self._delay_for_unlocked(model_name, input_tokens)
                if delay <= 1e-9:
                    now = self.clock()
                    ms = self.model_stats[model_name]
                    ps = self.provider_stats[self.pool.model(model_name).provider.name]
                    ms.starts.append((now, input_tokens))
                    ps.starts.append((now, input_tokens))
                    ms.seconds_waited += waited
                    ms.requests += 1
                    ps.requests += 1
                    self._save_state_unlocked()
                    return waited
            self.sleeper(delay)
            waited += delay

    def wait_for_provider(self, provider_name: str) -> float:
        """Space listing calls by the provider's rps; decide under the lock, sleep outside it, then decide again."""
        p_spec = self.pool.providers()[provider_name]
        spacing = self.pool.share / (p_spec.rps * self.pool.safety) if p_spec.rps and p_spec.rps > 0 else 0.0
        waited = 0.0
        while True:
            with self._lock():
                self._load_state_unlocked()
                ps = self.provider_stats[provider_name]
                delay = max(0.0, ps.starts[-1][0] + spacing - self.clock()) if spacing > 0 and ps.starts else 0.0
                if delay <= 1e-9:
                    ps.starts.append((self.clock(), 0))
                    self._save_state_unlocked()
                    return waited
            self.sleeper(delay)
            waited += delay

    def record_result(self, model_name: str, prompt_tokens: int, output_tokens: int) -> None:
        with self._lock():
            self._load_state_unlocked()
            m_spec = self.pool.model(model_name)
            ms = self.model_stats[model_name]
            ps = self.provider_stats[m_spec.provider.name]
            if ms.starts:
                ms.starts[-1] = (ms.starts[-1][0], prompt_tokens)
            if ps.starts:
                ps.starts[-1] = (ps.starts[-1][0], prompt_tokens)
            ms.prompt_tokens += prompt_tokens
            ms.output_tokens += output_tokens
            ps.prompt_tokens += prompt_tokens
            ps.output_tokens += output_tokens

            today_m = self._current_date_str(m_spec.provider)
            ms.daily_counts[today_m] = ms.daily_counts.get(today_m, 0) + 1
            ps.daily_counts[today_m] = ps.daily_counts.get(today_m, 0) + 1

            if m_spec.provider.tokens_per_month is not None:
                month = self._current_month_str(m_spec.provider)
                ps.monthly_tokens[month] = ps.monthly_tokens.get(month, 0) + prompt_tokens + output_tokens

            ms.consecutive_successes += 1
            if ms.consecutive_successes >= 10:
                ms.adaptive_factor = min(1.0, ms.adaptive_factor * 1.1)
            self._save_state_unlocked()

    def _calc_reset_ts(self, verdict: QuotaVerdict, now: float, is_monthly: bool, provider: ProviderSpec) -> float:
        if verdict.reset_time is not None:
            return verdict.reset_time.timestamp()
        if verdict.retry_delay is not None:
            return now + verdict.retry_delay
        if is_monthly:
            return monthly_reset(self.pool, provider, now).reset_utc.timestamp()
        return next_reset(self.pool, provider, now).reset_utc.timestamp()

    def _record_rejection_unlocked(self, model_name: str, verdict: QuotaVerdict) -> None:
        now = self.clock()
        m_spec = self.pool.model(model_name)
        ms = self.model_stats[model_name]
        ps = self.provider_stats[m_spec.provider.name]

        ms.retries[verdict.kind] = ms.retries.get(verdict.kind, 0) + 1
        ps.retries[verdict.kind] = ps.retries.get(verdict.kind, 0) + 1

        if verdict.server_limit_value is not None and verdict.kind in ("MINUTE_TOKENS", "MINUTE_REQUESTS", "DAILY"):
            key = "tpm_input" if verdict.kind == "MINUTE_TOKENS" else ("rpm" if verdict.kind == "MINUTE_REQUESTS" else "rpd")
            self._record_learned_limit_unlocked(model_name, key, verdict.server_limit_value, verdict.scope)

        if verdict.kind in ("MINUTE_TOKENS", "MINUTE_REQUESTS"):
            ms.consecutive_successes = 0
            ms.adaptive_factor = max(0.25, ms.adaptive_factor * 0.75)
            m_starts = [t for t, _ in ms.starts if now - t < 60.0]
            ms.cooldown_until = now + max(verdict.retry_delay or 30.0, (m_starts[0] + 60.0 - now) if m_starts else 0.0) + self.rng.uniform(1.0, 5.0)
        elif verdict.kind in ("DAILY", "MONTHLY"):
            reset_ts = self._calc_reset_ts(verdict, now, verdict.kind == "MONTHLY", m_spec.provider)
            if verdict.kind == "DAILY" and verdict.scope != "provider":
                ms.exhausted_until = reset_ts
            else:
                for m in self.pool.models().values():
                    if m.provider.name == m_spec.provider.name:
                        self.model_stats[m.name].exhausted_until = reset_ts
                ps.exhausted_until = reset_ts

    def record_rejection(self, model_name: str, verdict: QuotaVerdict) -> None:
        with self._lock():
            self._load_state_unlocked()
            self._record_rejection_unlocked(model_name, verdict)
            self._save_state_unlocked()

    def _remaining_today_unlocked(self, model_name: str) -> int | None:
        m_spec = self.pool.model(model_name)
        ms = self.model_stats[model_name]
        ps = self.provider_stats[m_spec.provider.name]
        rpd = ms.learned_limits.get("rpd") or ps.learned_limits.get("rpd") or m_spec.rpd or m_spec.provider.rpd
        if rpd is None:
            return None
        used = ms.daily_counts.get(self._current_date_str(m_spec.provider), 0)
        return max(0, rpd - used)

    def remaining_today(self, model_name: str) -> int | None:
        with self._lock():
            self._load_state_unlocked()
            return self._remaining_today_unlocked(model_name)

    def _exhausted_until_unlocked(self, model_name: str) -> datetime | None:
        m_spec = self.pool.model(model_name)
        ms = self.model_stats[model_name]
        ps = self.provider_stats[m_spec.provider.name]
        now = self.clock()

        ts_candidates = []
        if ms.exhausted_until and ms.exhausted_until > now:
            ts_candidates.append(ms.exhausted_until)
        if ps.exhausted_until and ps.exhausted_until > now:
            ts_candidates.append(ps.exhausted_until)

        rem = self._remaining_today_unlocked(model_name)
        if rem is not None and rem == 0:
            ts_candidates.append(next_reset(self.pool, m_spec.provider, now).reset_utc.timestamp())

        if m_spec.provider.tokens_per_month is not None:
            if ps.monthly_tokens.get(self._current_month_str(m_spec.provider), 0) >= m_spec.provider.tokens_per_month:
                ts_candidates.append(monthly_reset(self.pool, m_spec.provider, now).reset_utc.timestamp())

        if not ts_candidates:
            return None
        return datetime.fromtimestamp(max(ts_candidates), tz=timezone.utc)

    def exhausted_until(self, model_name: str) -> datetime | None:
        with self._lock():
            self._load_state_unlocked()
            return self._exhausted_until_unlocked(model_name)

    def _build_model_report(self, m_name: str, m_spec: ModelSpec, now: float) -> ModelReport:
        ms = self.model_stats[m_name]
        ps = self.provider_stats[m_spec.provider.name]
        eff = effective(self.pool, m_spec, ms.adaptive_factor, ms.learned_limits)
        daily_lim = ms.learned_limits.get("rpd") or ps.learned_limits.get("rpd") or eff.rpd
        return ModelReport(
            adaptive_factor=ms.adaptive_factor,
            requests=ms.requests,
            retries=dict(ms.retries),
            seconds_waited=ms.seconds_waited,
            prompt_tokens=ms.prompt_tokens,
            output_tokens=ms.output_tokens,
            effective_limits={"rpm": eff.rpm, "tpm_input": eff.tpm_input},
            learned_limits=dict(ms.learned_limits),
            count_today=ms.daily_counts.get(self._current_date_str(m_spec.provider), 0),
            daily_limit=daily_lim,
            cooldown_end=ms.cooldown_until if ms.cooldown_until > now else None,
            exhausted_until=self._exhausted_until_unlocked(m_name),
        )

    def _build_provider_report(self, p_name: str, p_spec: ProviderSpec) -> tuple[ProviderReport, bool]:
        ps = self.provider_stats[p_name]
        is_unv = not bool(p_spec.verified_on)
        rep = ProviderReport(
            requests=ps.requests,
            retries=dict(ps.retries),
            seconds_waited=ps.seconds_waited,
            prompt_tokens=ps.prompt_tokens,
            output_tokens=ps.output_tokens,
            monthly_tokens=ps.monthly_tokens.get(self._current_month_str(p_spec), 0),
            unverified=is_unv,
        )
        return rep, is_unv

    def report(self) -> GovernorReport:
        with self._lock():
            self._load_state_unlocked()
            models_rep, providers_rep, unverified = {}, {}, []
            now = self.clock()

            for m_name, m_spec in self.pool.models().items():
                models_rep[m_name] = self._build_model_report(m_name, m_spec, now)

            for p_name, p_spec in self.pool.providers().items():
                prep, is_unv = self._build_provider_report(p_name, p_spec)
                providers_rep[p_name] = prep
                if is_unv:
                    unverified.append(p_name)

            return GovernorReport(
                models=models_rep,
                providers=providers_rep,
                unverified_providers=unverified,
                corrupt_state=self.corrupt_state,
            )

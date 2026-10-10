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
"""
from __future__ import annotations

import fcntl, json, math, random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from tools.outsourcing.limits import ModelSpec, Pool, ProviderSpec, effective, monthly_reset, next_reset
from tools.outsourcing.quota import QuotaVerdict


@dataclass
class ModelStats:
    adaptive_factor: float = 1.0; consecutive_successes: int = 0; requests: int = 0; retries: dict[str, int] = field(default_factory=dict); seconds_waited: float = 0.0; prompt_tokens: int = 0; output_tokens: int = 0; cooldown_until: float = 0.0; exhausted_until: float | None = None; learned_limits: dict[str, int] = field(default_factory=dict); starts: list[tuple[float, int]] = field(default_factory=list); daily_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ProviderStats:
    requests: int = 0; retries: dict[str, int] = field(default_factory=dict); seconds_waited: float = 0.0; prompt_tokens: int = 0; output_tokens: int = 0; cooldown_until: float = 0.0; exhausted_until: float | None = None; learned_limits: dict[str, int] = field(default_factory=dict); starts: list[tuple[float, int]] = field(default_factory=list); daily_counts: dict[str, int] = field(default_factory=dict); monthly_tokens: dict[str, int] = field(default_factory=dict)


@dataclass
class ModelReport:
    adaptive_factor: float; requests: int; retries: dict[str, int]; seconds_waited: float; prompt_tokens: int; output_tokens: int; effective_limits: dict; learned_limits: dict; count_today: int; daily_limit: int | None; cooldown_end: float | None; exhausted_until: datetime | None


@dataclass
class ProviderReport:
    requests: int; retries: dict[str, int]; seconds_waited: float; prompt_tokens: int; output_tokens: int; monthly_tokens: int; unverified: bool


@dataclass
class GovernorReport:
    models: dict[str, ModelReport]; providers: dict[str, ProviderReport]; unverified_providers: list[str]; corrupt_state: bool = False


class Governor:

    def __init__(self, pool: Pool, state_path: Path | str, clock: Callable[[], float], sleeper: Callable[[float], None], rng: random.Random | None = None) -> None:
        self.pool, self.state_path, self.clock, self.sleeper = pool, Path(state_path), clock, sleeper
        self.rng, self.corrupt_state = rng or random.Random(), False
        self.model_stats, self.provider_stats = {m: ModelStats() for m in pool.models()}, {p: ProviderStats() for p in pool.providers()}
        self._load_state()

    def _lock_and_run(self, mode: str, fn: Callable):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.state_path.parent / f"{self.state_path.name}.lock"
        with open(lock_file, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try: return fn()
            finally: fcntl.flock(f, fcntl.LOCK_UN)

    def _load_state(self) -> None:
        def do_load():
            if not self.state_path.exists(): return
            try:
                text = self.state_path.read_text(encoding="utf-8")
                if not text.strip(): return
                data = json.loads(text)
            except Exception:
                self.corrupt_state = True
                for ms in self.model_stats.values(): ms.adaptive_factor = 0.75
                return
            now = self.clock()
            for m, md in data.get("models", {}).items():
                if m in self.model_stats:
                    ms = self.model_stats[m]
                    ms.adaptive_factor = 0.75 if self.corrupt_state else md.get("adaptive_factor", 1.0)
                    ms.consecutive_successes, ms.cooldown_until, ms.exhausted_until = md.get("consecutive_successes", 0), md.get("cooldown_until", 0.0), md.get("exhausted_until")
                    ms.learned_limits, ms.starts, ms.daily_counts = md.get("learned_limits", {}), [(t, tok) for t, tok in md.get("starts", []) if now - t < 60.0], md.get("daily_counts", {})
            for p, pd in data.get("providers", {}).items():
                if p in self.provider_stats:
                    ps = self.provider_stats[p]
                    ps.cooldown_until, ps.exhausted_until, ps.learned_limits = pd.get("cooldown_until", 0.0), pd.get("exhausted_until"), pd.get("learned_limits", {})
                    ps.starts, ps.daily_counts, ps.monthly_tokens = [(t, tok) for t, tok in pd.get("starts", []) if now - t < 60.0], pd.get("daily_counts", {}), pd.get("monthly_tokens", {})
            self._clean_old_counts()
        self._lock_and_run("r", do_load)

    def _save_state(self) -> None:
        def do_save():
            data = {
                "models": {m: {"adaptive_factor": ms.adaptive_factor, "consecutive_successes": ms.consecutive_successes, "cooldown_until": ms.cooldown_until, "exhausted_until": ms.exhausted_until, "learned_limits": ms.learned_limits, "starts": ms.starts, "daily_counts": ms.daily_counts} for m, ms in self.model_stats.items()},
                "providers": {p: {"cooldown_until": ps.cooldown_until, "exhausted_until": ps.exhausted_until, "learned_limits": ps.learned_limits, "starts": ps.starts, "daily_counts": ps.daily_counts, "monthly_tokens": ps.monthly_tokens} for p, ps in self.provider_stats.items()},
            }
            temp_file = self.state_path.parent / f"{self.state_path.name}.tmp"
            temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp_file.replace(self.state_path)
        self._lock_and_run("w", do_save)

    def _current_date_str(self, provider: ProviderSpec) -> str: return next_reset(self.pool, provider, self.clock()).reset_provider.strftime("%Y-%m-%d")
    def _current_month_str(self, provider: ProviderSpec) -> str: return next_reset(self.pool, provider, self.clock()).reset_provider.strftime("%Y-%m")

    def _clean_old_counts(self) -> None:
        for m_spec in self.pool.models().values():
            self.model_stats[m_spec.name].daily_counts = {k: v for k, v in self.model_stats[m_spec.name].daily_counts.items() if k == self._current_date_str(m_spec.provider)}
        for p_spec in self.pool.providers().values():
            ps, today, month = self.provider_stats[p_spec.name], self._current_date_str(p_spec), self._current_month_str(p_spec)
            ps.daily_counts, ps.monthly_tokens = {k: v for k, v in ps.daily_counts.items() if k == today}, {k: v for k, v in ps.monthly_tokens.items() if k == month}

    def _clean_starts(self, now: float) -> None:
        for ms in self.model_stats.values(): ms.starts = [(t, tok) for t, tok in ms.starts if now - t < 60.0]
        for ps in self.provider_stats.values(): ps.starts = [(t, tok) for t, tok in ps.starts if now - t < 60.0]

    def record_learned_limit(self, model_name: str, key: str, value: int, scope: str = "model") -> None:
        self._load_state()
        m_spec, ps = self.pool.model(model_name), self.provider_stats[self.pool.model(model_name).provider.name]
        ms = self.model_stats[model_name]
        target, cfg = (ps, getattr(m_spec.provider, key, None)) if scope == "provider" or (getattr(m_spec, key, None) is None and getattr(m_spec.provider, key, None) is not None) else (ms, getattr(m_spec, key, None))
        if cfg is None or value < cfg: target.learned_limits[key] = min(target.learned_limits.get(key, value), value)
        self._save_state()

    def delay_for(self, model_name: str, input_tokens: int) -> float:
        self._load_state()
        now = self.clock()
        self._clean_starts(now)
        m_spec = self.pool.model(model_name)
        ms, ps = self.model_stats[model_name], self.provider_stats[m_spec.provider.name]
        delays = [0.0]
        if ms.cooldown_until > now: delays.append(ms.cooldown_until - now)
        if ps.cooldown_until > now: delays.append(ps.cooldown_until - now)

        eff = effective(self.pool, m_spec, ms.adaptive_factor, ms.learned_limits)
        if eff.rpm is not None:
            mr = [t for t, _ in ms.starts if now - t < 60.0]
            if len(mr) >= eff.rpm: delays.append(mr[len(mr) - eff.rpm] + 60.0 - now)
        if eff.model_spacing > 0 and ms.starts: delays.append(ms.starts[-1][0] + eff.model_spacing - now)

        if eff.tpm_input is not None:
            mrt = sum(tok for t, tok in ms.starts if now - t < 60.0)
            if ms.starts and (mrt + input_tokens > eff.tpm_input):
                accum = mrt + input_tokens
                for t, tok in ms.starts:
                    accum -= tok; delays.append(t + 60.0 - now)
                    if accum <= eff.tpm_input: break

        p_cfg_rpm = ps.learned_limits.get("rpm", m_spec.provider.rpm)
        if p_cfg_rpm is not None:
            p_eff_rpm = max(1, math.floor(p_cfg_rpm * self.pool.safety * ms.adaptive_factor / self.pool.share))
            pr = [t for t, _ in ps.starts if now - t < 60.0]
            if len(pr) >= p_eff_rpm: delays.append(pr[len(pr) - p_eff_rpm] + 60.0 - now)

        p_cfg_tpm = ps.learned_limits.get("tpm_input", m_spec.provider.tpm_input)
        if p_cfg_tpm is not None:
            p_eff_tpm = max(1, math.floor(p_cfg_tpm * self.pool.safety * ms.adaptive_factor / self.pool.share))
            prt = sum(tok for t, tok in ps.starts if now - t < 60.0)
            if ps.starts and (prt + input_tokens > p_eff_tpm):
                accum = prt + input_tokens
                for t, tok in ps.starts:
                    accum -= tok; delays.append(t + 60.0 - now)
                    if accum <= p_eff_tpm: break

        if eff.rps_spacing > 0 and ps.starts: delays.append(ps.starts[-1][0] + eff.rps_spacing - now)
        return max(0.0, max(delays))

    def wait_for_slot(self, model_name: str, input_tokens: int) -> float:
        waited = 0.0
        while True:
            delay = self.delay_for(model_name, input_tokens)
            if delay <= 1e-9: break
            self.sleeper(delay); waited += delay
        now = self.clock()
        ms, ps = self.model_stats[model_name], self.provider_stats[self.pool.model(model_name).provider.name]
        ms.starts.append((now, input_tokens)); ps.starts.append((now, input_tokens))
        ms.seconds_waited += waited; ms.requests, ps.requests = ms.requests + 1, ps.requests + 1
        self._save_state()
        return waited

    def wait_for_provider(self, provider_name: str) -> float:
        self._load_state()
        now, p_spec, ps = self.clock(), self.pool.providers()[provider_name], self.provider_stats[provider_name]
        rps_sp = self.pool.share / (p_spec.rps * self.pool.safety) if p_spec.rps and p_spec.rps > 0 else 0.0
        waited = 0.0
        if rps_sp > 0 and ps.starts:
            delay = max(0.0, ps.starts[-1][0] + rps_sp - now)
            if delay > 0: self.sleeper(delay); waited = delay
        ps.starts.append((self.clock(), 0))
        self._save_state()
        return waited

    def record_result(self, model_name: str, prompt_tokens: int, output_tokens: int) -> None:
        self._load_state()
        m_spec = self.pool.model(model_name)
        ms, ps = self.model_stats[model_name], self.provider_stats[m_spec.provider.name]
        if ms.starts: ms.starts[-1] = (ms.starts[-1][0], prompt_tokens)
        if ps.starts: ps.starts[-1] = (ps.starts[-1][0], prompt_tokens)
        ms.prompt_tokens, ms.output_tokens = ms.prompt_tokens + prompt_tokens, ms.output_tokens + output_tokens
        ps.prompt_tokens, ps.output_tokens = ps.prompt_tokens + prompt_tokens, ps.output_tokens + output_tokens

        today_m = self._current_date_str(m_spec.provider)
        ms.daily_counts[today_m] = ms.daily_counts.get(today_m, 0) + 1
        ps.daily_counts[today_m] = ps.daily_counts.get(today_m, 0) + 1

        if m_spec.provider.tokens_per_month is not None:
            month = self._current_month_str(m_spec.provider)
            ps.monthly_tokens[month] = ps.monthly_tokens.get(month, 0) + prompt_tokens + output_tokens

        ms.consecutive_successes += 1
        if ms.consecutive_successes >= 10: ms.adaptive_factor = min(1.0, ms.adaptive_factor * 1.1)
        self._save_state()

    def record_rejection(self, model_name: str, verdict: QuotaVerdict) -> None:
        self._load_state()
        now, m_spec = self.clock(), self.pool.model(model_name)
        ms, ps = self.model_stats[model_name], self.provider_stats[m_spec.provider.name]

        ms.retries[verdict.kind] = ms.retries.get(verdict.kind, 0) + 1
        ps.retries[verdict.kind] = ps.retries.get(verdict.kind, 0) + 1

        if verdict.server_limit_value is not None and verdict.kind in ("MINUTE_TOKENS", "MINUTE_REQUESTS"):
            self.record_learned_limit(model_name, "tpm_input" if verdict.kind == "MINUTE_TOKENS" else "rpm", verdict.server_limit_value, verdict.scope)

        if verdict.kind in ("MINUTE_TOKENS", "MINUTE_REQUESTS"):
            ms.consecutive_successes, ms.adaptive_factor = 0, max(0.25, ms.adaptive_factor * 0.75)
            m_starts = [t for t, _ in ms.starts if now - t < 60.0]
            ms.cooldown_until = now + max(verdict.retry_delay or 30.0, (m_starts[0] + 60.0 - now) if m_starts else 0.0) + self.rng.uniform(1.0, 5.0)
        elif verdict.kind == "DAILY":
            reset_ts = next_reset(self.pool, m_spec.provider, now).reset_utc.timestamp()
            if verdict.scope == "provider":
                for m in self.pool.models().values():
                    if m.provider.name == m_spec.provider.name: self.model_stats[m.name].exhausted_until = reset_ts
                ps.exhausted_until = reset_ts
            else: ms.exhausted_until = reset_ts
        elif verdict.kind == "MONTHLY":
            reset_ts = monthly_reset(self.pool, m_spec.provider, now).reset_utc.timestamp()
            for m in self.pool.models().values():
                if m.provider.name == m_spec.provider.name: self.model_stats[m.name].exhausted_until = reset_ts
            ps.exhausted_until = reset_ts
        self._save_state()

    def remaining_today(self, model_name: str) -> int | None:
        self._load_state()
        m_spec = self.pool.model(model_name)
        rpd = m_spec.rpd or m_spec.provider.rpd
        if rpd is None: return None
        return max(0, rpd - self.model_stats[model_name].daily_counts.get(self._current_date_str(m_spec.provider), 0))

    def exhausted_until(self, model_name: str) -> datetime | None:
        self._load_state()
        m_spec = self.pool.model(model_name)
        ms, ps = self.model_stats[model_name], self.provider_stats[m_spec.provider.name]
        now = self.clock()

        ts_candidates = []
        if ms.exhausted_until and ms.exhausted_until > now: ts_candidates.append(ms.exhausted_until)
        if ps.exhausted_until and ps.exhausted_until > now: ts_candidates.append(ps.exhausted_until)

        rem = self.remaining_today(model_name)
        if rem is not None and rem == 0: ts_candidates.append(next_reset(self.pool, m_spec.provider, now).reset_utc.timestamp())

        if m_spec.provider.tokens_per_month is not None:
            if ps.monthly_tokens.get(self._current_month_str(m_spec.provider), 0) >= m_spec.provider.tokens_per_month:
                ts_candidates.append(monthly_reset(self.pool, m_spec.provider, now).reset_utc.timestamp())

        if not ts_candidates: return None
        return datetime.fromtimestamp(max(ts_candidates), tz=timezone.utc)

    def report(self) -> GovernorReport:
        self._load_state()
        models_rep, providers_rep, unverified = {}, {}, []
        now = self.clock()

        for m_name, m_spec in self.pool.models().items():
            ms = self.model_stats[m_name]
            eff = effective(self.pool, m_spec, ms.adaptive_factor, ms.learned_limits)
            models_rep[m_name] = ModelReport(
                adaptive_factor=ms.adaptive_factor, requests=ms.requests, retries=dict(ms.retries),
                seconds_waited=ms.seconds_waited, prompt_tokens=ms.prompt_tokens, output_tokens=ms.output_tokens,
                effective_limits={"rpm": eff.rpm, "tpm_input": eff.tpm_input}, learned_limits=dict(ms.learned_limits),
                count_today=ms.daily_counts.get(self._current_date_str(m_spec.provider), 0), daily_limit=eff.rpd,
                cooldown_end=ms.cooldown_until if ms.cooldown_until > now else None,
                exhausted_until=self.exhausted_until(m_name),
            )

        for p_name, p_spec in self.pool.providers().items():
            ps = self.provider_stats[p_name]
            is_unv = not bool(p_spec.verified_on)
            if is_unv: unverified.append(p_name)
            providers_rep[p_name] = ProviderReport(
                requests=ps.requests, retries=dict(ps.retries), seconds_waited=ps.seconds_waited,
                prompt_tokens=ps.prompt_tokens, output_tokens=ps.output_tokens,
                monthly_tokens=ps.monthly_tokens.get(self._current_month_str(p_spec), 0), unverified=is_unv,
            )

        return GovernorReport(models=models_rep, providers=providers_rep, unverified_providers=unverified, corrupt_state=self.corrupt_state)

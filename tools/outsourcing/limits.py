"""Load and validate model pool configuration, effective limits, and resets.

CAPABILITIES:
  CAP-OUTSOURCING-LIMITS: Model pool specification loading and limit calculations. [tests: test_limits, test_acceptance_wo_1_0_10]
INPUTS AND OUTPUTS:
  Loads config JSON and provides Pool, ProviderSpec, ModelSpec, effective limits, and next reset times.
CONTRACTS: none.
INVARIANTS:
  - Effective limits are adjusted for safety and share.
NOT IN SCOPE:
  - Runtime request counting or network calls.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
  2026-10-11 WP-1.0 FR-1.0-14 (Claude): a repeated model rank is refused (B1: rank is unique).
  2026-10-11 WP-1.0 FR-1.0-14 (Claude, owner's BLK-1.0-12 answer): optional per-model reasoning_effort, temperature,
    top_p and timeout_seconds.
"""
from __future__ import annotations

import json
import math
import zoneinfo
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

VALID_RISK_TIERS = {"T1", "T2", "T3"}


class LimitsError(Exception):
    """Raised when pool loading or limit calculation fails."""


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    api: str
    base_url: str
    enabled: bool
    tier: str
    verified_on: str
    day_reset: str
    data_use: str
    rpm: int | None = None
    rps: float | None = None
    tpm_input: int | None = None
    rpd: int | None = None
    tokens_per_month: int | None = None


@dataclass(frozen=True)
class ModelSpec:
    name: str
    provider: ProviderSpec
    rank: int
    risk_tiers: tuple[str, ...]
    max_input_tokens: int
    max_output_tokens: int
    rpm: int | None = None
    tpm_input: int | None = None
    rpd: int | None = None
    reasoning_effort: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    timeout_seconds: int | None = None


@dataclass(frozen=True)
class EffectiveLimits:
    rpm: int | None
    tpm_input: int | None
    rps_spacing: float
    model_spacing: float
    rpd: int | None
    tokens_per_month: int | None
    input_token_ceiling: int


@dataclass(frozen=True)
class ResetTimes:
    reset_utc: datetime
    reset_provider: datetime
    reset_karachi: datetime
    used_fallback: bool = False


class Pool:

    def __init__(
        self,
        share: int,
        safety: float,
        providers: dict[str, ProviderSpec],
        models: dict[str, ModelSpec],
    ) -> None:
        self.share = share
        self.safety = safety
        self._providers = providers
        self._models = models

    def providers(self) -> dict[str, ProviderSpec]:
        return dict(self._providers)

    def models(self) -> dict[str, ModelSpec]:
        return dict(self._models)

    def model(self, name: str) -> ModelSpec:
        if name not in self._models:
            raise LimitsError(f"Unknown model: '{name}'")
        spec = self._models[name]
        if not spec.provider.enabled:
            raise LimitsError(f"Model '{name}' belongs to disabled provider '{spec.provider.name}'")
        return spec

    def candidates(self, risk_tier: str) -> list[ModelSpec]:
        res = [m for m in self._models.values() if m.provider.enabled and risk_tier in m.risk_tiers]
        res.sort(key=lambda m: m.rank)
        return res


def _load_raw_data(path_or_dict: str | Path | dict) -> dict:
    if isinstance(path_or_dict, (str, Path)):
        p = Path(path_or_dict)
        if not p.exists():
            raise LimitsError(f"Pool file not found: {p}")
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            raise LimitsError(f"Invalid JSON: {e}")
    if isinstance(path_or_dict, dict):
        return path_or_dict
    raise LimitsError("Pool data must be path or dict")


def _parse_providers(providers_raw: object) -> dict[str, ProviderSpec]:
    if not isinstance(providers_raw, dict):
        raise LimitsError("Key 'providers' must be dictionary")
    providers: dict[str, ProviderSpec] = {}
    for pname, pdata in providers_raw.items():
        if not isinstance(pdata, dict):
            raise LimitsError(f"Provider '{pname}' must be object")
        api, base_url, enabled = pdata.get("api"), pdata.get("base_url"), pdata.get("enabled")
        if api not in ("gemini", "openai") or not isinstance(base_url, str) or not isinstance(enabled, bool):
            raise LimitsError(f"Provider '{pname}' fields invalid")
        tier, verified_on, day_reset = pdata.get("tier"), pdata.get("verified_on", ""), pdata.get("day_reset")
        if not isinstance(tier, str) or not isinstance(verified_on, str) or not isinstance(day_reset, str):
            raise LimitsError(f"Provider '{pname}' string fields invalid")
        rps_val = float(pdata["rps"]) if "rps" in pdata and pdata["rps"] is not None else None
        providers[pname] = ProviderSpec(
            name=pname,
            api=api,
            base_url=base_url.rstrip("/"),
            enabled=enabled,
            tier=tier,
            verified_on=verified_on,
            day_reset=day_reset,
            data_use=pdata.get("data_use", ""),
            rpm=pdata.get("rpm"),
            rps=rps_val,
            tpm_input=pdata.get("tpm_input"),
            rpd=pdata.get("rpd"),
            tokens_per_month=pdata.get("tokens_per_month"),
        )
    return providers


def _parse_models(models_raw: object, providers: dict[str, ProviderSpec]) -> dict[str, ModelSpec]:
    if not isinstance(models_raw, dict):
        raise LimitsError("Key 'models' must be dictionary")
    models: dict[str, ModelSpec] = {}
    for mname, mdata in models_raw.items():
        if not isinstance(mdata, dict):
            raise LimitsError(f"Model '{mname}' must be object")
        pname = mdata.get("provider")
        if pname not in providers:
            raise LimitsError(f"Model '{mname}' references unknown provider '{pname}'")
        rank = mdata.get("rank")
        if not isinstance(rank, int) or rank <= 0:
            raise LimitsError(f"Model '{mname}' rank invalid")
        same_rank = [other.name for other in models.values() if other.rank == rank]
        if same_rank:
            raise LimitsError(f"Models '{same_rank[0]}' and '{mname}' share rank {rank}; ranks must be unique")
        risk_tiers_raw = mdata.get("risk_tiers")
        if not isinstance(risk_tiers_raw, list) or not risk_tiers_raw or not set(risk_tiers_raw).issubset(VALID_RISK_TIERS):
            raise LimitsError(f"Model '{mname}' risk_tiers invalid")
        max_in, max_out = mdata.get("max_input_tokens"), mdata.get("max_output_tokens")
        if not isinstance(max_in, int) or max_in <= 0 or not isinstance(max_out, int) or max_out <= 0:
            raise LimitsError(f"Model '{mname}' max tokens invalid")
        models[mname] = ModelSpec(
            name=mname,
            provider=providers[pname],
            rank=rank,
            risk_tiers=tuple(risk_tiers_raw),
            max_input_tokens=max_in,
            max_output_tokens=max_out,
            rpm=mdata.get("rpm"),
            tpm_input=mdata.get("tpm_input"),
            rpd=mdata.get("rpd"),
            **_request_parameters(mname, mdata),
        )
    return models


def _request_parameters(mname: str, mdata: dict) -> dict:
    """The optional per-model request parameters (BLK-1.0-12): validated, or a LimitsError naming the field."""
    effort, temp, top_p, timeout = (mdata.get(k) for k in ("reasoning_effort", "temperature", "top_p", "timeout_seconds"))
    if effort is not None and (not isinstance(effort, str) or not effort.strip()):
        raise LimitsError(f"Model '{mname}' reasoning_effort must be a non-empty string")
    if temp is not None and (isinstance(temp, bool) or not isinstance(temp, (int, float)) or not 0 <= temp <= 2):
        raise LimitsError(f"Model '{mname}' temperature must be a number from 0 to 2")
    if top_p is not None and (isinstance(top_p, bool) or not isinstance(top_p, (int, float)) or not 0 < top_p <= 1):
        raise LimitsError(f"Model '{mname}' top_p must be a number above 0 and at most 1")
    if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0):
        raise LimitsError(f"Model '{mname}' timeout_seconds must be a positive integer")
    return {"reasoning_effort": effort, "temperature": None if temp is None else float(temp),
            "top_p": None if top_p is None else float(top_p), "timeout_seconds": timeout}


def load_pool(path_or_dict: str | Path | dict) -> Pool:
    data = _load_raw_data(path_or_dict)
    if not isinstance(data, dict):
        raise LimitsError("Pool root must be object")
    share = data.get("share")
    if not isinstance(share, int) or share < 1:
        raise LimitsError("Key 'share' must be integer >= 1")
    safety = data.get("safety")
    if not isinstance(safety, (int, float)) or not (0.5 <= safety <= 1.0):
        raise LimitsError("Key 'safety' must be float 0.5..1.0")
    providers = _parse_providers(data.get("providers"))
    models = _parse_models(data.get("models"), providers)
    return Pool(share=share, safety=safety, providers=providers, models=models)


def effective(
    pool: Pool,
    model: ModelSpec,
    adaptive_factor: float = 1.0,
    server_limits: dict[str, int] | None = None,
) -> EffectiveLimits:
    sl = server_limits or {}
    safety, share = pool.safety, pool.share

    def calc_eff(cfg_val: int | None, key: str) -> int | None:
        val = sl.get(key, cfg_val) if key in sl and sl[key] is not None else cfg_val
        if val is None:
            return None
        return max(1, math.floor(val * safety * adaptive_factor / share))

    eff_rpm = calc_eff(model.rpm, "rpm")
    eff_tpm = calc_eff(model.tpm_input, "tpm_input")
    rps_sp = share / (model.provider.rps * safety) if model.provider.rps and model.provider.rps > 0 else 0.0
    model_sp = 60.0 / eff_rpm if eff_rpm and eff_rpm > 0 else 0.0

    prov_tpm = model.provider.tpm_input
    m_tpm_raw = sl.get("tpm_input", model.tpm_input)
    ceil_tpm = math.floor(m_tpm_raw * safety) if m_tpm_raw is not None else model.max_input_tokens
    if prov_tpm is not None:
        ceil_tpm = min(ceil_tpm, math.floor(prov_tpm * safety))

    return EffectiveLimits(
        rpm=eff_rpm,
        tpm_input=eff_tpm,
        rps_spacing=rps_sp,
        model_spacing=model_sp,
        rpd=model.rpd,
        tokens_per_month=model.provider.tokens_per_month,
        input_token_ceiling=min(model.max_input_tokens, ceil_tpm),
    )


def _la_offset(dt_utc: datetime) -> timedelta:
    year = dt_utc.year
    m1 = datetime(year, 3, 1, tzinfo=timezone.utc)
    d_start = datetime(year, 3, (m1 + timedelta(days=(6 - m1.weekday()) % 7) + timedelta(days=7)).day, 10, 0, tzinfo=timezone.utc)
    n1 = datetime(year, 11, 1, tzinfo=timezone.utc)
    d_end = datetime(year, 11, (n1 + timedelta(days=(6 - n1.weekday()) % 7)).day, 9, 0, tzinfo=timezone.utc)
    if d_start <= dt_utc < d_end:
        return timedelta(hours=-7)
    return timedelta(hours=-8)


def _resolve_tz(tz_name: str) -> tuple[datetime.tzinfo | None, bool]:
    try:
        return zoneinfo.ZoneInfo(tz_name), False
    except zoneinfo.ZoneInfoNotFoundError:
        if tz_name == "America/Los_Angeles":
            return None, True
        if tz_name == "Asia/Karachi":
            return timezone(timedelta(hours=5)), True
        if tz_name == "UTC":
            return timezone.utc, True
        raise LimitsError(f"Unsupported timezone: '{tz_name}'")


def next_reset(pool: Pool | None, provider_or_zone: ProviderSpec | str, now_utc: datetime | float) -> ResetTimes:
    if isinstance(now_utc, (int, float)):
        now_dt = datetime.fromtimestamp(now_utc, tz=timezone.utc)
    else:
        now_dt = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
    tz_name = provider_or_zone.day_reset if isinstance(provider_or_zone, ProviderSpec) else provider_or_zone
    prov_tz, used_fallback = _resolve_tz(tz_name)
    if prov_tz is None and tz_name == "America/Los_Angeles":
        local_now = now_dt.astimezone(timezone(_la_offset(now_dt)))
    else:
        local_now = now_dt.astimezone(prov_tz)
    next_mid = (local_now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    reset_utc = next_mid.astimezone(timezone.utc)
    try:
        karachi_tz: datetime.tzinfo = zoneinfo.ZoneInfo("Asia/Karachi")
    except zoneinfo.ZoneInfoNotFoundError:
        karachi_tz = timezone(timedelta(hours=5))
    return ResetTimes(reset_utc=reset_utc, reset_provider=next_mid, reset_karachi=reset_utc.astimezone(karachi_tz), used_fallback=used_fallback)


def monthly_reset(pool: Pool | None, provider_or_zone: ProviderSpec | str, now_utc: datetime | float) -> ResetTimes:
    res = next_reset(pool, provider_or_zone, now_utc)
    next_m = (res.reset_provider.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    reset_utc = next_m.astimezone(timezone.utc)
    try:
        karachi_tz: datetime.tzinfo = zoneinfo.ZoneInfo("Asia/Karachi")
    except zoneinfo.ZoneInfoNotFoundError:
        karachi_tz = timezone(timedelta(hours=5))
    return ResetTimes(reset_utc=reset_utc, reset_provider=next_m, reset_karachi=reset_utc.astimezone(karachi_tz), used_fallback=res.used_fallback)

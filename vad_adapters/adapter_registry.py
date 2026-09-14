"""
vad_adapters/adapter_registry.py

One Job:
    Maintain a validated lookup mapping from canonical adapter / operating point names
    to ready-to-call VAD adapter instances conforming to VADAdapterContract.

What this module must NEVER do:
    - Never include adapter-specific inference logic, scoring heuristics, or thresholds.
    - Never return an adapter instance that has not passed check_adapter_conformance.
    - Never silently ignore unknown adapter requests or return None on failure.
    - Never let orchestrator.py or any downstream file import concrete adapter modules directly.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

from vad_adapters.adapter_contract import (
    ContractValidationError,
    VADAdapterContract,
    check_adapter_conformance,
)

logger = logging.getLogger(__name__)

AdapterFactory = Callable[..., VADAdapterContract]


# ==============================================================================
# Exceptions
# ==============================================================================

class RegistryError(Exception):
    """Base exception for adapter registry errors."""
    pass


class UnknownAdapterError(RegistryError, KeyError):
    """Raised when an requested adapter name is not registered."""
    pass


class DuplicateAdapterError(RegistryError, ValueError):
    """Raised when attempting to register an adapter name that is already registered."""
    pass


# ==============================================================================
# Registry Class
# ==============================================================================

class AdapterRegistry:
    """
    Registry managing factory bindings and instantiation for VAD adapters.

    Guarantees:
        1. All registered names resolve to VADAdapterContract instances.
        2. Every returned adapter passes check_adapter_conformance before delivery.
        3. WebRTC operating modes (0-3) are registered as distinct, independent entries.
    """

    def __init__(self) -> None:
        self._factories: Dict[str, AdapterFactory] = {}

    def register(
        self,
        name: str,
        factory: AdapterFactory,
        allow_override: bool = False,
    ) -> None:
        """
        Registers an adapter factory under a unique canonical name.

        Duplicate Registration Policy:
            Treating duplicate registration as a strict error by default protects
            against subtle test contamination or accidental overwrites. If replacement
            is explicitly intended (e.g. mock injection in unit tests), `allow_override=True`
            must be provided.

        Args:
            name: Canonical name string (e.g. 'ten_vad', 'webrtc_vad_mode2').
            factory: Callable producing a VADAdapterContract instance.
            allow_override: If True, allows replacing an existing registration.

        Raises:
            ValueError: If name is empty or invalid.
            DuplicateAdapterError: If name is already registered and allow_override is False.
        """
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Adapter registration name cannot be empty.")

        if clean_name in self._factories and not allow_override:
            raise DuplicateAdapterError(
                f"Adapter '{clean_name}' is already registered. "
                "Set allow_override=True if replacement is intentional."
            )

        self._factories[clean_name] = factory
        logger.debug("Registered VAD adapter factory: '%s'", clean_name)

    def unregister(self, name: str) -> None:
        """Removes an adapter factory registration."""
        if name in self._factories:
            del self._factories[name]
            logger.debug("Unregistered VAD adapter factory: '%s'", name)

    def is_registered(self, name: str) -> bool:
        """Check if an adapter name is currently registered."""
        return name in self._factories

    def list_registered(self) -> List[str]:
        """Return a sorted list of all currently registered adapter names."""
        return sorted(self._factories.keys())

    def get(
        self,
        name: str,
        hardware_policy: str = "cpu_only",
        **kwargs: Any,
    ) -> VADAdapterContract:
        """
        Instantiates, validates, and returns an adapter by canonical name.

        Args:
            name: Canonical adapter identifier.
            hardware_policy: Hardware device policy ('cpu_only' or 'gpu_for_firered').
            **kwargs: Additional parameters passed to the adapter factory.

        Returns:
            A ready-to-call VADAdapterContract instance verified by check_adapter_conformance.

        Raises:
            UnknownAdapterError: If name is not registered.
            ContractValidationError: If instantiated adapter fails contract conformance.
        """
        if name not in self._factories:
            available = ", ".join(repr(k) for k in self.list_registered())
            raise UnknownAdapterError(
                f"Unknown adapter requested: '{name}'. Available registered adapters: [{available}]"
            )

        factory = self._factories[name]
        try:
            adapter = factory(hardware_policy=hardware_policy, **kwargs)
        except TypeError:
            # Fallback for factories that don't accept hardware_policy (e.g. WebRTC)
            adapter = factory(**kwargs)

        # Fail loudly immediately if the adapter violates contract
        check_adapter_conformance(adapter)

        return adapter

    def resolve_adapter_names(
        self,
        active_adapters: Sequence[str],
        webrtc_modes: Optional[Sequence[int]] = None,
    ) -> List[str]:
        """
        Resolves high-level config adapter names into discrete registered operating point names.

        Specifically, if 'webrtc_vad' is specified in active_adapters, it is expanded into
        the individual configured operating points ('webrtc_vad_mode0', etc.).

        Args:
            active_adapters: List of adapter names from run_config.yaml (e.g. ['ten_vad', 'webrtc_vad']).
            webrtc_modes: List of integer modes (0-3) to include when 'webrtc_vad' is present.

        Returns:
            List of discrete canonical names matching registered operating points.

        Raises:
            UnknownAdapterError: If an unrecognized adapter name is supplied.
        """
        modes = webrtc_modes if webrtc_modes is not None else [0, 1, 2, 3]
        resolved_names: List[str] = []

        for name in active_adapters:
            clean_name = name.strip()
            if clean_name == "webrtc_vad":
                for mode in modes:
                    if mode not in (0, 1, 2, 3):
                        raise ValueError(f"Invalid WebRTC mode {mode}. Expected 0, 1, 2, or 3.")
                    mode_name = f"webrtc_vad_mode{mode}"
                    if not self.is_registered(mode_name):
                        raise UnknownAdapterError(
                            f"WebRTC mode '{mode_name}' is not registered in the adapter registry."
                        )
                    resolved_names.append(mode_name)
            else:
                if not self.is_registered(clean_name):
                    available = ", ".join(repr(k) for k in self.list_registered())
                    raise UnknownAdapterError(
                        f"Requested active adapter '{clean_name}' is not registered. Available: [{available}]"
                    )
                resolved_names.append(clean_name)

        return resolved_names

    def build_active_adapters(
        self,
        active_adapters: Sequence[str],
        webrtc_modes: Optional[Sequence[int]] = None,
        hardware_policy: str = "cpu_only",
    ) -> Dict[str, VADAdapterContract]:
        """
        Resolves and instantiates all requested active adapters.

        Returns:
            Dictionary mapping resolved adapter names to validated adapter instances.
        """
        resolved_names = self.resolve_adapter_names(active_adapters, webrtc_modes=webrtc_modes)
        adapters: Dict[str, VADAdapterContract] = {}
        for name in resolved_names:
            adapters[name] = self.get(name, hardware_policy=hardware_policy)
        return adapters


# ==============================================================================
# Built-in Lazy Factories
# ==============================================================================

def _create_ten_vad(hardware_policy: str = "cpu_only", **kwargs: Any) -> VADAdapterContract:
    from vad_adapters.ten_vad_adapter import TENVADAdapter
    return TENVADAdapter(hardware_policy=hardware_policy, **kwargs)


def _create_firered_vad(hardware_policy: str = "cpu_only", **kwargs: Any) -> VADAdapterContract:
    from vad_adapters.firered_vad_adapter import FireRedVADAdapter
    return FireRedVADAdapter(hardware_policy=hardware_policy, **kwargs)


def _create_webrtc_vad_mode0(**kwargs: Any) -> VADAdapterContract:
    from vad_adapters.webrtc_vad_adapter import WebRTCVADAdapter
    return WebRTCVADAdapter(mode=0, **kwargs)


def _create_webrtc_vad_mode1(**kwargs: Any) -> VADAdapterContract:
    from vad_adapters.webrtc_vad_adapter import WebRTCVADAdapter
    return WebRTCVADAdapter(mode=1, **kwargs)


def _create_webrtc_vad_mode2(**kwargs: Any) -> VADAdapterContract:
    from vad_adapters.webrtc_vad_adapter import WebRTCVADAdapter
    return WebRTCVADAdapter(mode=2, **kwargs)


def _create_webrtc_vad_mode3(**kwargs: Any) -> VADAdapterContract:
    from vad_adapters.webrtc_vad_adapter import WebRTCVADAdapter
    return WebRTCVADAdapter(mode=3, **kwargs)


# ==============================================================================
# Global Registry Instance & Module-Level Convenience Functions
# ==============================================================================

_GLOBAL_REGISTRY = AdapterRegistry()

# Register the standard six baseline operating points
_GLOBAL_REGISTRY.register("ten_vad", _create_ten_vad)
_GLOBAL_REGISTRY.register("firered_vad", _create_firered_vad)
_GLOBAL_REGISTRY.register("webrtc_vad_mode0", _create_webrtc_vad_mode0)
_GLOBAL_REGISTRY.register("webrtc_vad_mode1", _create_webrtc_vad_mode1)
_GLOBAL_REGISTRY.register("webrtc_vad_mode2", _create_webrtc_vad_mode2)
_GLOBAL_REGISTRY.register("webrtc_vad_mode3", _create_webrtc_vad_mode3)


def register_adapter(
    name: str,
    factory: AdapterFactory,
    allow_override: bool = False,
) -> None:
    """Register an adapter factory in the global registry."""
    _GLOBAL_REGISTRY.register(name, factory, allow_override=allow_override)


def get_adapter(
    name: str,
    hardware_policy: str = "cpu_only",
    **kwargs: Any,
) -> VADAdapterContract:
    """Retrieve an instantiated and conformance-validated adapter from the global registry."""
    return _GLOBAL_REGISTRY.get(name, hardware_policy=hardware_policy, **kwargs)


def list_registered_adapters() -> List[str]:
    """List all registered adapter names in the global registry."""
    return _GLOBAL_REGISTRY.list_registered()


def resolve_active_adapter_names(
    active_adapters: Sequence[str],
    webrtc_modes: Optional[Sequence[int]] = None,
) -> List[str]:
    """Resolve high-level active adapter names to discrete registered names."""
    return _GLOBAL_REGISTRY.resolve_adapter_names(active_adapters, webrtc_modes=webrtc_modes)


def build_active_adapters(
    active_adapters: Sequence[str],
    webrtc_modes: Optional[Sequence[int]] = None,
    hardware_policy: str = "cpu_only",
) -> Dict[str, VADAdapterContract]:
    """Build and validate all configured active adapters from the global registry."""
    return _GLOBAL_REGISTRY.build_active_adapters(
        active_adapters,
        webrtc_modes=webrtc_modes,
        hardware_policy=hardware_policy,
    )
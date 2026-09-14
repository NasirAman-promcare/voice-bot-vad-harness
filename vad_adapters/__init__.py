"""
vad_adapters package initialization.

Exposes the standardized adapter contract, decision record schema, frame
chunking utilities, adapter registry, and conformance verification helpers.
"""

from vad_adapters.adapter_contract import (
    AudioChunk,
    ContractValidationError,
    DecisionRecord,
    VADAdapterContract,
    check_adapter_conformance,
    chunk_audio_stream,
    validate_decision_record,
)
from vad_adapters.adapter_registry import (
    AdapterFactory,
    AdapterRegistry,
    DuplicateAdapterError,
    RegistryError,
    UnknownAdapterError,
    build_active_adapters,
    get_adapter,
    list_registered_adapters,
    register_adapter,
    resolve_active_adapter_names,
)

__all__ = [
    # Contract & Schema
    "AudioChunk",
    "ContractValidationError",
    "DecisionRecord",
    "VADAdapterContract",
    "check_adapter_conformance",
    "chunk_audio_stream",
    "validate_decision_record",
    # Registry
    "AdapterFactory",
    "AdapterRegistry",
    "DuplicateAdapterError",
    "RegistryError",
    "UnknownAdapterError",
    "build_active_adapters",
    "get_adapter",
    "list_registered_adapters",
    "register_adapter",
    "resolve_active_adapter_names",
]
"""Metadata enums (Section 18).

Authoritative definitions for equation source, validation status,
and WORLD7 alignment tags used throughout the sector library.
"""

from __future__ import annotations

from enum import Enum


class EquationSource(Enum):
    """Source classification for sector equations (Section 18.1)."""

    MEADOWS_SPEC = "meadows_spec"
    WORLD3_RECONSTRUCTED = "world3_reconstructed"
    EMPIRICAL_FIT = "empirical_fit"
    ADAPTER_DERIVED = "adapter_derived"
    SYNTHESIZED_FROM_PRIMARY_LITERATURE = "synthesized_from_primary_literature"
    CANONICAL_TEST_WORLD = "canonical_test_world"
    PLACEHOLDER = "placeholder"


class ValidationStatus(Enum):
    """Validation state of a sector (Section 18.2)."""

    REFERENCE_MATCHED = "reference_matched"
    EMPIRICALLY_ANCHORED = "empirically_anchored"
    STRUCTURAL_PLACEHOLDER = "structural_placeholder"
    EXPERIMENTAL = "experimental"


class WORLD7Alignment(Enum):
    """Alignment with WORLD7 model (Section 18.3)."""

    DIRECT = "direct"
    APPROXIMATE = "approximate"
    NONE = "none"

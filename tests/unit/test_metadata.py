"""Tests for metadata enums (Section 18)."""

from __future__ import annotations

from pyworldx.core.metadata import (
    EquationSource,
    ValidationStatus,
    WORLD7Alignment,
)


class TestEquationSource:
    def test_all_values(self) -> None:
        assert EquationSource.MEADOWS_SPEC.value == "meadows_spec"
        assert EquationSource.WORLD3_RECONSTRUCTED.value == "world3_reconstructed"
        assert EquationSource.EMPIRICAL_FIT.value == "empirical_fit"
        assert EquationSource.ADAPTER_DERIVED.value == "adapter_derived"
        assert EquationSource.SYNTHESIZED_FROM_PRIMARY_LITERATURE.value == (
            "synthesized_from_primary_literature"
        )
        assert EquationSource.PLACEHOLDER.value == "placeholder"

    def test_count(self) -> None:
        assert len(EquationSource) == 6


class TestValidationStatus:
    def test_all_values(self) -> None:
        assert ValidationStatus.REFERENCE_MATCHED.value == "reference_matched"
        assert ValidationStatus.EMPIRICALLY_ANCHORED.value == "empirically_anchored"
        assert ValidationStatus.STRUCTURAL_PLACEHOLDER.value == "structural_placeholder"
        assert ValidationStatus.EXPERIMENTAL.value == "experimental"

    def test_count(self) -> None:
        assert len(ValidationStatus) == 4


class TestWORLD7Alignment:
    def test_all_values(self) -> None:
        assert WORLD7Alignment.DIRECT.value == "direct"
        assert WORLD7Alignment.APPROXIMATE.value == "approximate"
        assert WORLD7Alignment.NONE.value == "none"

    def test_count(self) -> None:
        assert len(WORLD7Alignment) == 3

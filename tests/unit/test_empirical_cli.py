"""Phase 3: Tests for the CLI registry-resolution helper in empirical.py.

These tests document the CORRECT behavior and will be RED until
_resolve_registry() is implemented to replace the broken for_sector/subset
calls in the CLI block.
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from pyworldx.calibration.empirical import _resolve_registry  # noqa: F401


class TestResolveRegistryAllSectors:
    """No --params flag: return all parameters for the given sector."""

    def test_population_sector_returns_3_names(self) -> None:
        args = SimpleNamespace(sector="population", params=None)
        reg, names = _resolve_registry(args)
        assert len(names) == 3

    def test_capital_sector_returns_4_names(self) -> None:
        args = SimpleNamespace(sector="capital", params=None)
        reg, names = _resolve_registry(args)
        assert len(names) == 4

    def test_agriculture_sector_returns_4_names(self) -> None:
        args = SimpleNamespace(sector="agriculture", params=None)
        reg, names = _resolve_registry(args)
        assert len(names) == 4

    def test_resources_sector_returns_2_names(self) -> None:
        args = SimpleNamespace(sector="resources", params=None)
        reg, names = _resolve_registry(args)
        assert len(names) == 2

    def test_pollution_sector_returns_3_names(self) -> None:
        args = SimpleNamespace(sector="pollution", params=None)
        reg, names = _resolve_registry(args)
        assert len(names) == 3

    def test_returns_full_registry_not_subset(self) -> None:
        """Registry must be the full 16-param registry, not a sector slice."""
        args = SimpleNamespace(sector="population", params=None)
        reg, names = _resolve_registry(args)
        assert reg.size == 16

    def test_name_strings_exist_in_registry(self) -> None:
        args = SimpleNamespace(sector="capital", params=None)
        reg, names = _resolve_registry(args)
        for name in names:
            entry = reg.lookup(name)  # must not raise
            assert entry.sector_owner == "capital"


class TestResolveRegistryWithParamsFlag:
    """--params flag: return only the explicitly requested names."""

    def test_single_valid_param(self) -> None:
        args = SimpleNamespace(sector="population", params="population.len_scale")
        reg, names = _resolve_registry(args)
        assert names == ["population.len_scale"]

    def test_multiple_valid_params(self) -> None:
        args = SimpleNamespace(
            sector="capital",
            params="capital.icor,capital.alic",
        )
        reg, names = _resolve_registry(args)
        assert set(names) == {"capital.icor", "capital.alic"}

    def test_params_stripped_of_whitespace(self) -> None:
        args = SimpleNamespace(sector="capital", params="  capital.icor , capital.alic  ")
        reg, names = _resolve_registry(args)
        assert "capital.icor" in names
        assert "capital.alic" in names

    def test_unknown_param_raises_value_error(self) -> None:
        args = SimpleNamespace(sector="population", params="does.not.exist")
        with pytest.raises(ValueError, match="Unknown parameter"):
            _resolve_registry(args)

    def test_cross_sector_param_allowed(self) -> None:
        """--params can reference a param from a different sector (power-user mode)."""
        args = SimpleNamespace(sector="population", params="capital.icor")
        reg, names = _resolve_registry(args)
        assert names == ["capital.icor"]


class TestResolveRegistryEdgeCases:

    def test_unknown_sector_with_no_params_raises_value_error(self) -> None:
        args = SimpleNamespace(sector="nonexistent_sector", params=None)
        with pytest.raises(ValueError, match="No parameters found"):
            _resolve_registry(args)

    def test_empty_params_string_falls_back_to_sector(self) -> None:
        """Empty --params string should behave like --params not provided."""
        args = SimpleNamespace(sector="resources", params="")
        reg, names = _resolve_registry(args)
        assert len(names) == 2

    def test_params_with_only_whitespace_falls_back_to_sector(self) -> None:
        args = SimpleNamespace(sector="resources", params="   ")
        reg, names = _resolve_registry(args)
        assert len(names) == 2

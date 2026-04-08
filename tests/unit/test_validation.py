"""Tests for validation module."""

from __future__ import annotations

import tempfile

import numpy as np

from pyworldx.core.result import RunResult
from pyworldx.sectors.welfare import WelfareSector
from pyworldx.validation.regression_tests import (
    RegressionCheckResult,
    check_regression,
    load_reference_trajectory,
)
from pyworldx.validation.sector_tests import (
    SectorTestResult,
    check_metadata_completeness,
)


class TestSectorTestResult:
    def test_construction(self) -> None:
        r = SectorTestResult(
            sector_name="test_sector",
            test_name="unit_check",
            passed=True,
            message="",
        )
        assert r.sector_name == "test_sector"
        assert r.passed is True

    def test_with_failure_message(self) -> None:
        r = SectorTestResult(
            sector_name="test_sector",
            test_name="unit_check",
            passed=False,
            message="Something failed",
        )
        assert not r.passed
        assert "failed" in r.message


class TestCheckMetadataCompleteness:
    def test_welfare_sector_passes(self) -> None:
        sector = WelfareSector()
        result = check_metadata_completeness(sector)
        assert result.passed

    def test_sector_name_in_result(self) -> None:
        sector = WelfareSector()
        result = check_metadata_completeness(sector)
        assert result.sector_name == "welfare"


class TestRegressionCheckResult:
    def test_construction(self) -> None:
        r = RegressionCheckResult(
            variable="POP",
            max_relative_error=0.001,
            max_absolute_error=1000.0,
            tolerance=0.01,
            passed=True,
            worst_time=1980.0,
        )
        assert r.variable == "POP"
        assert r.passed is True
        assert r.worst_time == 1980.0


class TestLoadReferenceTrajectory:
    def test_load_csv(self) -> None:
        csv_content = "t,POP,R\n0,1.65e9,1e12\n1,1.7e9,9.8e11\n2,1.75e9,9.6e11\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            f.flush()
            ref = load_reference_trajectory(f.name)

        assert "t" in ref
        assert "POP" in ref
        assert "R" in ref
        assert len(ref["t"]) == 3

    def test_missing_file_raises(self) -> None:
        try:
            load_reference_trajectory("/nonexistent/path/to/file.csv")
            assert False, "Should have raised"
        except FileNotFoundError:
            pass

    def test_with_comment_lines(self) -> None:
        csv_content = "# This is a comment\nt,X\n0,10\n1,20\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            f.flush()
            ref = load_reference_trajectory(f.name)

        assert "t" in ref
        assert "X" in ref
        assert len(ref["t"]) == 2


class TestCheckRegression:
    def test_matching_data_passes(self) -> None:
        t = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        pop = np.array([1.65e9, 1.7e9, 1.75e9, 1.8e9, 1.85e9])
        result = RunResult(
            time_index=t,
            trajectories={"POP": pop},
        )
        reference = {
            "t": t,
            "POP": pop,  # exact match
        }
        report = check_regression(result, reference, variables=["POP"])
        assert report.all_passed

    def test_divergent_data_fails(self) -> None:
        t = np.array([0.0, 1.0, 2.0])
        result = RunResult(
            time_index=t,
            trajectories={"X": np.array([1.0, 2.0, 3.0])},
        )
        reference = {
            "t": t,
            "X": np.array([1.0, 2.0, 100.0]),  # big divergence at t=2
        }
        report = check_regression(
            result, reference, variables=["X"], relative_tol=0.01
        )
        assert not report.all_passed

    def test_missing_time_column(self) -> None:
        result = RunResult(
            time_index=np.array([0.0]),
            trajectories={"X": np.array([1.0])},
        )
        reference = {"X": np.array([1.0])}  # no "t"
        report = check_regression(result, reference)
        assert not report.all_passed

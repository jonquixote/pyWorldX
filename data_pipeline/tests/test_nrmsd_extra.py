"""Tests for NRMSD calibration — additional coverage."""

from __future__ import annotations

import numpy as np
import pytest

from data_pipeline.calibration.nrmsd import (
    nrmsd_direct,
    nrmsd_change_rate,
    weighted_nrmsd,
    compare_calibrated_series,
)


class TestNrmsdDirectRealWorld:
    """NRMSD tests with realistic climate/economics data."""
    
    def test_temperature_anomaly(self):
        """Temperature anomaly should have low NRMSD if models match."""
        # Simulated NASA GISS data
        model = np.array([-0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
        reference = np.array([-0.18, -0.12, 0.02, 0.08, 0.22, 0.28, 0.42, 0.48, 0.62, 0.68])
        
        result = nrmsd_direct(model, reference)
        assert result < 0.1  # Good match should be < 10%
        assert result > 0  # Not perfect match
    
    def test_co2_emissions_growth(self):
        """CO2 emissions should show increasing trend."""
        # Simulated GCP data
        model = np.array([20000, 22000, 24000, 26000, 28000, 30000, 32000, 34000, 35000, 36000])
        reference = np.array([20500, 22200, 23800, 26200, 27800, 30500, 31800, 34200, 34800, 36500])
        
        result = nrmsd_direct(model, reference)
        assert result < 0.05  # Very good match
    
    def test_perfect_match_zero(self):
        """Identical series should give NRMSD = 0."""
        data = np.array([100.0, 200.0, 300.0, 400.0, 500.0])
        assert nrmsd_direct(data, data) == pytest.approx(0.0)
    
    def test_constant_reference_nan(self):
        """Constant reference with zero mean should give NaN."""
        model = np.array([1.0, 2.0, 3.0])
        reference = np.array([0.0, 0.0, 0.0])
        assert np.isnan(nrmsd_direct(model, reference))


class TestNrmsdChangeRateRealWorld:
    """Change rate NRMSD with realistic data."""
    
    def test_same_growth_rate_zero(self):
        """Same growth rate should give NRMSD = 0 on change rates."""
        model = np.array([100.0, 110.0, 121.0, 133.1])  # 10% growth
        reference = np.array([200.0, 220.0, 242.0, 266.2])  # 10% growth
        
        result = nrmsd_change_rate(model, reference)
        assert result == pytest.approx(0.0, abs=1e-6)
    
    def test_different_growth_rates(self):
        """Different growth rates should give positive NRMSD."""
        model = np.array([100.0, 110.0, 121.0, 133.1])  # 10% growth
        reference = np.array([100.0, 105.0, 110.25, 115.76])  # 5% growth
        
        result = nrmsd_change_rate(model, reference)
        assert result > 0
        assert np.isfinite(result)
    
    def test_volatile_data(self):
        """Volatile data should still compute."""
        model = np.array([10.0, 15.0, 8.0, 20.0, 12.0, 18.0])
        reference = np.array([11.0, 14.0, 9.0, 19.0, 13.0, 17.0])
        
        result = nrmsd_change_rate(model, reference)
        assert np.isfinite(result)


class TestWeightedNrmsdRealWorld:
    """Weighted NRMSD with multiple variables."""
    
    def test_climate_calibration(self):
        """Climate model calibration with multiple variables."""
        model = {
            "temperature": np.array([0.0, 0.1, 0.2, 0.3, 0.4]),
            "co2": np.array([280, 285, 290, 295, 300]),
        }
        reference = {
            "temperature": np.array([0.0, 0.08, 0.22, 0.28, 0.42]),
            "co2": np.array([280, 285, 290, 295, 300]),
        }
        
        # Temperature has slight error, CO2 is perfect
        result = weighted_nrmsd(model, reference)
        assert 0 < result < 0.1
    
    def test_missing_variable_ignored(self):
        """Missing variables in one dict should be ignored."""
        model = {"a": np.array([1.0, 2.0]), "b": np.array([10.0, 20.0])}
        reference = {"a": np.array([1.0, 2.0])}  # No 'b'
        
        result = weighted_nrmsd(model, reference)
        assert result == pytest.approx(0.0)  # Only 'a' compared
    
    def test_custom_weights(self):
        """Custom weights should affect the result."""
        model = {
            "temperature": np.array([0.0, 0.1, 0.2]),
            "co2": np.array([280, 285, 290]),
        }
        reference = {
            "temperature": np.array([0.0, 0.2, 0.4]),  # Big error
            "co2": np.array([280, 285, 290]),  # Perfect
        }
        
        # Weight temperature heavily
        result_high = weighted_nrmsd(model, reference, weights={"temperature": 0.9, "co2": 0.1})
        # Weight co2 heavily (but co2 is perfect)
        result_low = weighted_nrmsd(model, reference, weights={"temperature": 0.1, "co2": 0.9})
        
        assert result_high > result_low


class TestCompareCalibratedSeries:
    """Test CSV comparison function."""
    
    def test_identical_csvs(self, tmp_path):
        """Identical CSVs should give NRMSD = 0."""
        model_csv = tmp_path / "model.csv"
        ref_csv = tmp_path / "reference.csv"
        
        content = "# comment\nyear,value,quality_flag\n2020,100.0,OK\n2021,110.0,OK\n2022,120.0,OK\n"
        model_csv.write_text(content)
        ref_csv.write_text(content)
        
        result = compare_calibrated_series(model_csv, ref_csv)
        assert result["nrmsd_direct"] == pytest.approx(0.0)
        assert result["nrmsd_change_rate"] == pytest.approx(0.0)
        assert result["overlap_years"] == 3
    
    def test_different_csvs(self, tmp_path):
        """Different CSVs should give positive NRMSD."""
        model_csv = tmp_path / "model.csv"
        ref_csv = tmp_path / "reference.csv"
        
        model_csv.write_text(
            "# comment\nyear,value,quality_flag\n2020,100.0,OK\n2021,110.0,OK\n2022,120.0,OK\n"
        )
        ref_csv.write_text(
            "# comment\nyear,value,quality_flag\n2020,105.0,OK\n2021,115.0,OK\n2022,125.0,OK\n"
        )
        
        result = compare_calibrated_series(model_csv, ref_csv)
        assert result["nrmsd_direct"] > 0
        assert result["overlap_years"] == 3
    
    def test_partial_overlap(self, tmp_path):
        """Partial year overlap should use common years."""
        model_csv = tmp_path / "model.csv"
        ref_csv = tmp_path / "reference.csv"
        
        model_csv.write_text(
            "# comment\nyear,value,quality_flag\n2020,100.0,OK\n2021,110.0,OK\n2022,120.0,OK\n"
        )
        ref_csv.write_text(
            "# comment\nyear,value,quality_flag\n2021,110.0,OK\n2022,120.0,OK\n2023,130.0,OK\n"
        )
        
        result = compare_calibrated_series(model_csv, ref_csv)
        assert result["overlap_years"] == 2
        assert result["nrmsd_direct"] == pytest.approx(0.0)
    
    def test_no_overlap_returns_nan(self, tmp_path):
        """No overlapping years should return NaN."""
        model_csv = tmp_path / "model.csv"
        ref_csv = tmp_path / "reference.csv"
        
        model_csv.write_text(
            "# comment\nyear,value,quality_flag\n2020,100.0,OK\n"
        )
        ref_csv.write_text(
            "# comment\nyear,value,quality_flag\n2022,120.0,OK\n"
        )
        
        result = compare_calibrated_series(model_csv, ref_csv)
        assert np.isnan(result["nrmsd_direct"])

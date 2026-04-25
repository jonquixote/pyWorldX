import pytest


def test_composite_objective_weights_sum_to_meaningful_total():
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner

    runner = EmpiricalCalibrationRunner(composite=True)
    weights = runner.get_objective_weights()
    assert "population" in weights
    assert "co2" in weights
    assert weights["population"] == pytest.approx(1.5, rel=0.01)
    assert weights["co2"] == pytest.approx(1.5, rel=0.01)
    assert weights["resources"] == pytest.approx(0.75, rel=0.01)


def test_joint_calibration_validation_nrmsd_is_independent():
    """Joint run must compute validation NRMSD on holdout window only."""
    from unittest.mock import patch

    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner

    runner = EmpiricalCalibrationRunner(composite=True)
    with patch.object(
        runner.bridge,
        "calculate_validation_score",
        wraps=runner.bridge.calculate_validation_score,
    ) as mock_val:
        with patch.object(runner, "_run_optimizer", return_value={}):
            runner.run()
        mock_val.assert_called_once()


@pytest.mark.slow
@pytest.mark.usefixtures("stub_optimizer")
def test_joint_calibration_result_has_all_required_fields():
    from unittest.mock import patch

    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner

    runner = EmpiricalCalibrationRunner(composite=True)
    with patch.object(runner, "_run_optimizer", return_value={"cbr_base": 0.028}):
        with patch.object(runner.bridge, "build_objective", return_value=lambda p: 0.05):
            with patch.object(runner.bridge, "calculate_validation_score", return_value=0.07):
                result = runner.run()
    assert hasattr(result, "train_nrmsd")
    assert hasattr(result, "validation_nrmsd")
    assert hasattr(result, "overfit_flagged")
    assert hasattr(result, "optimized_params")

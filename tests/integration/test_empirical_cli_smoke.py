"""Smoke tests for the empirical CLI entry-point."""
import subprocess
import sys
from pathlib import Path
import pytest

class TestCliDryRun:
    """Invoke the CLI via subprocess so argparse / logging paths are exercised."""

    @pytest.fixture(autouse=True)
    def aligned_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "aligned"
        d.mkdir()
        self.aligned = d
        return d

    def _run_cli(self, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable, "-m", "pyworldx.calibration.empirical",
                "--sector", "population",
                "--aligned-dir", str(self.aligned),
                "--dry-run",
                *extra_args,
            ],
            capture_output=True,
            text=True,
        )

    def test_dry_run_exits_zero_on_empty_aligned_dir(self):
        proc = self._run_cli()
        assert "AttributeError" not in proc.stderr
        assert "ImportError" not in proc.stderr

    def test_dry_run_unknown_sector_exits_nonzero(self):
        proc = subprocess.run(
            [
                sys.executable, "-m", "pyworldx.calibration.empirical",
                "--sector", "__bad__",
                "--aligned-dir", str(self.aligned),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0
        assert "Traceback" not in proc.stderr

    def test_dry_run_module_import_succeeds(self):
        proc = subprocess.run(
            [
                sys.executable, "-c",
                "from pyworldx.calibration.empirical import _resolve_registry; print('OK')",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert "OK" in proc.stdout

"""Pytest configuration and markers for data_pipeline tests."""

from typing import Any



def pytest_configure(config: Any) -> None:
    config.addinivalue_line(
        "markers",
        "network: marks tests that require network access (deselect with '-m \"not network\"')",
    )

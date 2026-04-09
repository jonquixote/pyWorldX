"""Pytest configuration and markers for data_pipeline tests."""



def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "network: marks tests that require network access (deselect with '-m \"not network\"')",
    )

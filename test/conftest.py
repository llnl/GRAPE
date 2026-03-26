"""Shared pytest configuration for GRAPE's root test suite.

Pytest automatically imports `conftest.py` files without tests needing to
reference them directly. This is the standard pytest place to define shared
fixtures, hooks, and marker registration.
"""

from vine import grapeGit as git


def pytest_configure(config):
    """Register suite-wide pytest markers and default git flags for tests."""
    git.clearGitConfigFlags()
    git.addGitConfigFlag("-c protocol.file.allow=always")
    git.addGitConfigFlag("-c init.defaultBranch=master")

    config.addinivalue_line("markers", "publish: publish-focused tests")
    config.addinivalue_line("markers", "scenario: generated workspace scenario coverage")
    config.addinivalue_line("markers", "serial: tests that should stay in the serial lane")
    config.addinivalue_line("markers", "slow: tests with high wall-clock cost")

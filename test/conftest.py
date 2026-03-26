from vine import grapeGit as git


def pytest_configure(config):
    git.clearGitConfigFlags()
    git.addGitConfigFlag("-c protocol.file.allow=always")
    git.addGitConfigFlag("-c init.defaultBranch=master")

    config.addinivalue_line("markers", "publish: publish-focused tests")
    config.addinivalue_line("markers", "scenario: generated workspace scenario coverage")
    config.addinivalue_line("markers", "serial: tests that should stay in the serial lane")
    config.addinivalue_line("markers", "slow: tests with high wall-clock cost")

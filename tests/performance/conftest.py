import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-performance",
        action="store_true",
        default=False,
        help="run performance benchmark tests",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "performance: mark test as performance benchmark")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-performance"):
        return
    skip_perf = pytest.mark.skip(reason="need --run-performance option to run")
    for item in items:
        if "performance" in item.keywords or "tests/performance" in str(item.fspath):
            item.add_marker(skip_perf)

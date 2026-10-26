import matplotlib
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.getgroup("rangekeeper").addoption(
        "--show-plots",
        action="store_true",
        default=False,
        help="show Matplotlib plots during the test run",
    )


def pytest_configure(config: pytest.Config) -> None:
    if not config.getoption("show_plots"):
        matplotlib.use("Agg", force=True)


@pytest.fixture(autouse=True)
def configure_matplotlib_for_tests(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
):
    if request.config.getoption("show_plots"):
        yield
        return

    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda *args, **kwargs: None)
    try:
        yield
    finally:
        plt.close("all")

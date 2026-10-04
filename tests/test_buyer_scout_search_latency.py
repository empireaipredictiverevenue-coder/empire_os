import importlib
from pathlib import Path


search = importlib.import_module(
    "empire_os.search_fabric.search"
)

ROOT = Path(
    __file__
).resolve().parents[1]


class RecordingExecutor:
    observed_workers = []

    def __init__(
        self,
        *,
        max_workers,
    ):
        self.observed_workers.append(
            max_workers
        )

    def __enter__(self):
        return self

    def __exit__(
        self,
        *args,
    ):
        return False

    def map(
        self,
        fn,
        values,
    ):
        return [
            fn(value)
            for value in values
        ]


def _install_fake_search(
    monkeypatch,
):
    RecordingExecutor.observed_workers.clear()

    monkeypatch.setattr(
        search,
        "ThreadPoolExecutor",
        RecordingExecutor,
    )

    monkeypatch.setattr(
        search,
        "search_domains",
        lambda query, **kwargs: [
            query + ".example.com"
        ],
    )


def test_explicit_worker_budget_is_bounded(
    monkeypatch,
):
    _install_fake_search(
        monkeypatch
    )

    rows = (
        search.search_domains_parallel(
            [
                f"q{i}"
                for i in range(20)
            ],
            num=3,
            max_workers=99,
        )
    )

    assert (
        RecordingExecutor.observed_workers
        == [12]
    )

    assert len(rows) == 20


def test_default_worker_budget_remains_five(
    monkeypatch,
):
    _install_fake_search(
        monkeypatch
    )

    monkeypatch.delenv(
        "EMPIRE_SEARCH_PARALLEL_WORKERS",
        raising=False,
    )

    search.search_domains_parallel(
        [
            f"q{i}"
            for i in range(12)
        ],
        num=3,
    )

    assert (
        RecordingExecutor.observed_workers
        == [5]
    )


def test_environment_worker_budget_can_raise_service_concurrency(
    monkeypatch,
):
    _install_fake_search(
        monkeypatch
    )

    monkeypatch.setenv(
        "EMPIRE_SEARCH_PARALLEL_WORKERS",
        "8",
    )

    search.search_domains_parallel(
        [
            f"q{i}"
            for i in range(12)
        ],
        num=3,
    )

    assert (
        RecordingExecutor.observed_workers
        == [8]
    )


def test_invalid_environment_worker_budget_fails_to_safe_default(
    monkeypatch,
):
    _install_fake_search(
        monkeypatch
    )

    monkeypatch.setenv(
        "EMPIRE_SEARCH_PARALLEL_WORKERS",
        "invalid",
    )

    search.search_domains_parallel(
        [
            f"q{i}"
            for i in range(12)
        ],
        num=3,
    )

    assert (
        RecordingExecutor.observed_workers
        == [5]
    )


def test_runner_overlaps_independent_seed_lanes():
    text = (
        ROOT
        / "scripts"
        / "run_buyer_acquisition_scout.py"
    ).read_text()

    assert (
        "ThreadPoolExecutor"
        in text
    )

    assert (
        "public_future = executor.submit("
        in text
    )

    assert (
        "official_future = executor.submit("
        in text
    )

    assert (
        "search_fn=seed_search_fn"
        in text
    )

    assert (
        "seed_lane_workers"
        in text
    )


def test_runner_does_not_change_buyer_scout_search_callable_contract():
    text = (
        ROOT
        / "scripts"
        / "run_buyer_acquisition_scout.py"
    ).read_text()

    assert (
        "search_workers=search_workers"
        not in text
    )


def test_buyer_scout_keeps_two_argument_search_dependency():
    text = (
        ROOT
        / "empire_os"
        / "buyer_acquisition_scout.py"
    ).read_text()

    start = text.index(
        "def run_buyer_scout("
    )

    end = text.index(
        "\ndef refresh_buyer_scout(",
        start,
    )

    function = text[
        start:end
    ]

    assert (
        "search_workers:"
        not in function
    )

    search_call_start = function.index(
        "search_domains_parallel("
    )

    search_call_end = function.index(
        "if query_text and search_enabled",
        search_call_start,
    )

    search_call = function[
        search_call_start:
        search_call_end
    ]

    # Existing injected search functions accept only
    # (queries, num). Probe concurrency elsewhere in
    # run_buyer_scout legitimately uses max_workers.
    assert (
        "max_workers="
        not in search_call
    )

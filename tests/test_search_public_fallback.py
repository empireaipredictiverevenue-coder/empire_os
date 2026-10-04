from empire_os.search_fabric.public_fallback import (
    parse_public_search_html,
)


def test_brave_external_result_parses():
    page = """
    <html>
      <body>
        <div
          class="snippet any-random-class"
          data-pos="0"
          data-type="web"
          data-keynav="true"
        >
          <div class="result-body changed-class">
            <div class="result-content another-class">
              <a
                href="https://example.com/team/sahil-aggarwal"
                class="totally-different-hash l1"
              >
                <div>
                  Example Company
                </div>
                <div
                  class="title search-snippet-title changed-hash"
                  title="Sahil Aggarwal | Example Company"
                >
                  Sahil Aggarwal | Example Company
                </div>
              </a>
            </div>
          </div>
        </div>
      </body>
    </html>
    """

    rows = parse_public_search_html(
        page,
        provider="brave_web",
    )

    assert rows == [{
        "title":
            "Sahil Aggarwal | Example Company",
        "link":
            "https://example.com/team/sahil-aggarwal",
        "snippet": "",
        "position": 1,
        "engine": "brave_web",
    }]


def test_google_redirect_unwraps():
    page = """
    <html>
      <body>
        <a href="/url?q=https%3A%2F%2Fexample.org%2Fabout&sa=U">
          Chase Manning - Example Org
        </a>
      </body>
    </html>
    """

    rows = parse_public_search_html(
        page,
        provider="google_html",
    )

    assert rows[0]["link"] == (
        "https://example.org/about"
    )


def test_provider_navigation_is_not_evidence():
    page = """
    <html>
      <body>
        <a href="/settings">Settings</a>
        <a href="https://search.brave.com/help">
          Help
        </a>
      </body>
    </html>
    """

    assert (
        parse_public_search_html(
            page,
            provider="brave_web",
        )
        == []
    )


def test_captcha_page_fails_closed():
    page = """
    <html>
      <title>Verify you are human</title>
      <body>captcha</body>
    </html>
    """

    assert (
        parse_public_search_html(
            page,
            provider="google_html",
        )
        == []
    )


def test_resilient_search_recovery_uses_same_quality_gate(
    monkeypatch,
):
    import empire_os.search_fabric.search as exported_search
    import importlib

    module = importlib.import_module(
        "empire_os.search_fabric.search"
    )

    def primary(*args, **kwargs):
        return {
            "organic": [],
            "searchParameters": {
                "q":
                    '"Sahil Aggarwal"',
                "engine": "none",
            },
            "credits_left": 999999,
            "error":
                "All engines failed",
        }

    monkeypatch.setattr(
        module,
        "search",
        primary,
    )

    import empire_os.search_fabric.public_fallback as pf

    def fallback(*args, **kwargs):
        return [
            {
                "title":
                    "Sahil Aggarwal | Example Company",
                "link":
                    "https://example.com/sahil",
                "snippet": "",
                "position": 1,
                "engine":
                    "brave_web",
            },
            {
                "title":
                    "Completely unrelated result",
                "link":
                    "https://wrong.example/",
                "snippet": "",
                "position": 2,
                "engine":
                    "brave_web",
            },
        ]

    monkeypatch.setattr(
        pf,
        "search_public_web",
        fallback,
    )

    result = module.search_resilient(
        '"Sahil Aggarwal"',
        num=8,
        use_cache=False,
    )

    assert (
        result["searchParameters"][
            "engine"
        ]
        == "brave_web"
    )

    assert len(
        result["organic"]
    ) == 1

    assert (
        "Sahil Aggarwal"
        in result["organic"][0][
            "title"
        ]
    )


def test_brave_incidental_captcha_text_does_not_hide_real_results():
    page = """
    <html>
      <script>
        const labels = ["Blocked", "CAPTCHA"];
      </script>
      <div
        class="snippet svelte-jmfu5f"
        data-pos="0"
        data-type="web"
        data-keynav="true"
      >
        <div class="result-body">
          <div class="result-content">
            <a
              href="https://hig.com/team/sahil-aggarwal/"
              class="svelte-14r20fy l1"
            >
              <div>H.I.G. Capital</div>
              <div
                class="title search-snippet-title line-clamp-1"
                title="Sahil Aggarwal - Principal - Private Equity - H.I.G. Capital"
              >
                Sahil Aggarwal - Principal - Private Equity - H.I.G. Capital
              </div>
            </a>
          </div>
        </div>
      </div>
    </html>
    """

    rows = parse_public_search_html(
        page,
        provider="brave_web",
    )

    assert rows == [{
        "title":
            "Sahil Aggarwal - Principal - Private Equity - H.I.G. Capital",
        "link":
            "https://hig.com/team/sahil-aggarwal/",
        "snippet": "",
        "position": 1,
        "engine": "brave_web",
    }]


def test_brave_only_primary_l1_results_are_emitted():
    page = """
    <html>
      <div
        class="snippet"
        data-type="web"
      >
        <a
          class="svelte-14r20fy l1"
          href="https://example.com/person"
        >
          <div
            class="title search-snippet-title"
            title="Jane Doe - Founder - Example"
          >
            Jane Doe - Founder - Example
          </div>
        </a>

        <a
          class="thumbnail"
          href="https://youtube.com/watch?v=wrong"
        >
          Jane Doe unrelated video
        </a>
      </div>
    </html>
    """

    rows = parse_public_search_html(
        page,
        provider="brave_web",
    )

    assert len(rows) == 1

    assert (
        rows[0]["link"]
        == "https://example.com/person"
    )


def test_google_access_help_shell_returns_no_evidence():
    page = """
    <html>
      <body>
        <div>
          If you're having trouble accessing Google Search,
          please click here, or send feedback.
        </div>
        <a href="https://support.google.com/websearch">
          feedback
        </a>
      </body>
    </html>
    """

    assert (
        parse_public_search_html(
            page,
            provider="google_html",
        )
        == []
    )


def test_brave_cosmetic_class_hashes_can_change():
    page = """
    <html>
      <body>
        <div
          class="snippet future-hash-999"
          data-type="web"
          data-pos="4"
        >
          <a
            href="https://future.example/founder"
            class="future-random-css l1"
          >
            <div
              class="search-snippet-title absolutely-new-css"
              title="Alex Founder - Future Example"
            >
              Alex Founder - Future Example
            </div>
          </a>
        </div>
      </body>
    </html>
    """

    rows = parse_public_search_html(
        page,
        provider="brave_web",
    )

    assert len(rows) == 1
    assert (
        rows[0]["title"]
        == "Alex Founder - Future Example"
    )
    assert (
        rows[0]["link"]
        == "https://future.example/founder"
    )



def test_resilient_failure_is_provider_degraded(
    monkeypatch,
):
    import importlib

    module = importlib.import_module(
        "empire_os.search_fabric.search"
    )

    monkeypatch.setattr(
        module,
        "search",
        lambda *a, **k: {
            "organic": [],
            "searchParameters": {
                "q": '"Nobody"',
                "engine": "none",
                "search_state":
                    "PROVIDER_DEGRADED",
            },
            "error":
                "All engines failed",
        },
    )

    import empire_os.search_fabric.public_fallback as pf

    monkeypatch.setattr(
        pf,
        "search_public_web",
        lambda *a, **k: [],
    )

    monkeypatch.setattr(
        module,
        "_last_known_good_cache",
        lambda *a, **k: None,
    )

    result = module.search_resilient(
        '"Nobody"',
        use_cache=False,
    )

    assert (
        result["searchParameters"][
            "search_state"
        ]
        == "PROVIDER_DEGRADED"
    )

    assert (
        result[
            "search_operational_status"
        ]
        == "DEGRADED"
    )



def test_use_cache_false_never_writes_public_recovery(
    monkeypatch,
):
    import importlib

    module = importlib.import_module(
        "empire_os.search_fabric.search"
    )

    monkeypatch.setattr(
        module,
        "search",
        lambda *a, **k: {
            "organic": [],
            "searchParameters": {
                "q":
                    '"Cache Isolation"',
                "engine":
                    "none",
                "search_state":
                    "PROVIDER_DEGRADED",
            },
            "error":
                "All engines failed",
        },
    )

    import empire_os.search_fabric.public_fallback as pf

    monkeypatch.setattr(
        pf,
        "search_public_web",
        lambda *a, **k: [{
            "title":
                "Cache Isolation Real Company",
            "link":
                "https://realcompany.invalid/person",
            "snippet":
                "",
            "position":
                1,
            "engine":
                "brave_web",
        }],
    )

    def forbidden_write(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "use_cache=False wrote persistent cache"
        )

    monkeypatch.setattr(
        module,
        "_set_cache",
        forbidden_write,
    )

    result = module.search_resilient(
        '"Cache Isolation"',
        num=8,
        use_cache=False,
    )

    assert result["organic"]
    assert (
        result[
            "searchParameters"
        ]["cache"]
        is False
    )

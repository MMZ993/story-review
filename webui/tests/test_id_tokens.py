"""Deterministic tests for the proxy-hop ID-token module (id_tokens.py):
metadata minting with audience quoting, cache reuse, refresh margin, and
the empty-token failure. The metadata server is replaced by the injectable
_fetch/_now seams; no network is touched.
"""

import pytest

from webui import id_tokens


def fetch_returning(token="tok-1", expires="3600"):
    """A _fetch stand-in recording the URLs it served."""
    calls = []

    def _fetch(url):
        calls.append(url)
        return token, expires

    return _fetch, calls


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    """Isolate the module-level cache per test (it persists by design)."""
    monkeypatch.setattr(id_tokens, "_cache", None)


def test_mint_quotes_the_audience_into_the_metadata_url():
    _fetch, calls = fetch_returning()
    now = [1000.0]

    headers = id_tokens.metadata_id_token(
        "https://orchestration-run-url", _fetch=_fetch, _now=lambda: now[0]
    )

    assert headers == {"Authorization": "Bearer tok-1"}
    assert len(calls) == 1
    assert "audience=https%3A%2F%2Forchestration-run-url" in calls[0]
    assert "format=full" in calls[0]


def test_cached_token_is_reused_without_a_second_mint():
    _fetch, calls = fetch_returning()
    now = [1000.0]

    id_tokens.metadata_id_token("https://o", _fetch=_fetch, _now=lambda: now[0])
    id_tokens.metadata_id_token("https://o", _fetch=_fetch, _now=lambda: now[0])

    assert len(calls) == 1


def test_token_is_refreshed_before_the_stated_expiry():
    _fetch, calls = fetch_returning(expires="3600")
    now = [1000.0]

    def clock():
        return now[0]

    id_tokens.metadata_id_token("https://o", _fetch=_fetch, _now=clock)
    # Inside the refresh margin (expiry 4600, margin 60) → re-mint.
    now[0] = 4600.0
    id_tokens.metadata_id_token("https://o", _fetch=_fetch, _now=clock)

    assert len(calls) == 2


def test_empty_metadata_token_raises_oserror():
    _fetch, _ = fetch_returning(token="  ")

    with pytest.raises(OSError, match="empty token"):
        id_tokens.metadata_id_token("https://o", _fetch=_fetch, _now=lambda: 0.0)

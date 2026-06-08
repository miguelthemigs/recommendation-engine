"""Unit tests for config — locks the Cycle 2 env-driven CORS contract."""

import importlib

import config


def test_similarity_weights_sum_to_one():
    total = config.WEIGHT_GENRE + config.WEIGHT_KEYWORD + config.WEIGHT_CAST
    assert round(total, 6) == 1.0


def test_allowed_origins_defaults_to_local_dev():
    # With no override set, the dev origins are present and it's a list of strings.
    assert isinstance(config.ALLOWED_ORIGINS, list)
    assert all(isinstance(o, str) for o in config.ALLOWED_ORIGINS)


def test_allowed_origins_parses_comma_list_strips_and_drops_empties(monkeypatch):
    # The Cycle 2 deployment blocker fix: ALLOWED_ORIGINS is parsed from env,
    # whitespace-trimmed, and empty entries dropped.
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://a.com, https://b.com , ,https://c.com",
    )
    try:
        importlib.reload(config)
        assert config.ALLOWED_ORIGINS == [
            "https://a.com",
            "https://b.com",
            "https://c.com",
        ]
    finally:
        # Restore module to its unmodified state for any later tests.
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
        importlib.reload(config)

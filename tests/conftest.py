"""Hermetic test configuration: isolates unit/integration tests from local .env credentials."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_provider_credentials(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure standard tests never leak or depend on real .env API keys."""
    if request.node.get_closest_marker("live") is not None:
        return
    for key in ("SERV_API_KEY", "SERV_MODEL", "SERV_TEMPERATURE", "REPPO_API_KEY"):
        monkeypatch.delenv(key, raising=False)

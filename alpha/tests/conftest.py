"""Shared test fixtures."""

from __future__ import annotations

import pytest

# app/config.py calls load_dotenv() at import, so a developer's alpha/.env (or shell) can inject these
# into every test. They change pre-flight and write behaviour, so no test may depend on them by accident.
# A test that needs one sets it explicitly with monkeypatch.setenv.
_BEHAVIOUR_ENV = ("ALPHA_EXPECT_PROJECT", "ALPHA_DRY_RUN", "ALLOW_SAMPLE_DATA")


@pytest.fixture(autouse=True)
def _isolate_alpha_behaviour_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _BEHAVIOUR_ENV:
        monkeypatch.delenv(name, raising=False)

import asyncio
from types import SimpleNamespace

import pytest

from app.utils import asyncio_utils


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("win32", asyncio.SelectorEventLoop),
        ("linux", None),
    ],
)
def test_psycopg_loop_factory(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    expected: object | None,
) -> None:
    monkeypatch.setattr(asyncio_utils, "sys", SimpleNamespace(platform=platform))

    assert asyncio_utils.psycopg_loop_factory() is expected

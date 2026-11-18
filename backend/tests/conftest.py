"""Shared fixtures for the tests that exercise the real read path.

`build_dataset()` and `education.distributions()` are both `lru_cache`d, which is
right in production -- the frame is built once per process -- and a trap in tests:
the first test to load a dataset would pin it for every test after it, so a later
test pointed at a different directory would silently assert against the first one's
rows. Every fixture here clears both caches on the way in and on the way out.
"""
import os

import pytest

from app import config, data, education

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SYNTHETIC = os.path.join(FIXTURES, "ipeds_synthetic")


def _reset_caches() -> None:
    data.build_dataset.cache_clear()
    education.distributions.cache_clear()


@pytest.fixture
def data_dir(monkeypatch):
    """Point the app at a directory of CSVs, and leave no cached frame behind.

    Yields a setter so a test can choose its directory (the 13-institution fixture,
    the all-dropped one, or an empty tmp_path for the missing-file case).
    """
    def point_at(path: str) -> str:
        _reset_caches()
        monkeypatch.setattr(config, "DATA_DIR", str(path))
        return str(path)

    _reset_caches()
    yield point_at
    _reset_caches()


@pytest.fixture
def synthetic(data_dir):
    """The 13-institution fixture dataset, loaded through data.build_dataset()."""
    data_dir(SYNTHETIC)
    return data.build_dataset()

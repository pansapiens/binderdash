"""A misconfigured DATABASE must fail loudly, not degrade to noop.

Falling back to the noop repository on a URL we cannot honour would silently
discard designs, login history, and every API key while the app still reported
healthy. Leaving DATABASE unset stays the supported no-persistence path.
"""

import pytest

from backend.persistence.factory import create_repository
from backend.persistence.noop_repo import NoopDesignsRepository
from backend.persistence.sqlite_repo import SqliteDesignsRepository


@pytest.mark.parametrize("url", [None, "", "   "])
def test_unset_database_is_the_supported_noop_path(url):
    assert isinstance(create_repository(url), NoopDesignsRepository)


def test_sqlite_url_builds_a_real_repository(tmp_path):
    repo = create_repository(f"sqlite:///{tmp_path / 'x.sqlite'}")
    assert isinstance(repo, SqliteDesignsRepository)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:pw@localhost/binderdash",
        "postgres://user:pw@localhost/binderdash",
    ],
)
def test_postgres_url_raises_rather_than_silently_disabling(url):
    with pytest.raises(RuntimeError, match="not implemented"):
        create_repository(url)


def test_unknown_scheme_raises():
    with pytest.raises(RuntimeError, match="Unknown DATABASE scheme"):
        create_repository("mysql://localhost/binderdash")


def test_typo_in_sqlite_scheme_is_not_silently_ignored():
    # The failure this actually guards against: a typo'd scheme used to boot
    # cleanly with persistence off, so keys and designs vanished with no error.
    with pytest.raises(RuntimeError):
        create_repository("sqlit:///tmp/binderdash.sqlite")

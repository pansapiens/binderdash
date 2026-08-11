"""Tests for object-scoped design download JWTs."""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from backend.auth import ALGORITHM
from backend.download_tokens import (
    DEFAULT_TTL_SECONDS,
    DownloadTokenError,
    assert_designs_download_claims,
    mint_designs_download_token,
    verify_designs_download_token,
)
from backend.settings import SECRET_KEY


def test_mint_and_verify_round_trip() -> None:
    token = mint_designs_download_token("run-a", "tsv")
    claims = verify_designs_download_token(token)
    assert claims == {"run_id": "run-a", "format": "tsv"}


def test_verify_rejects_wrong_purpose() -> None:
    token = jwt.encode(
        {
            "purpose": "session",
            "run_id": "run-a",
            "format": "json",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    with pytest.raises(DownloadTokenError, match="not a designs download"):
        verify_designs_download_token(token)


def test_verify_rejects_expired() -> None:
    token = jwt.encode(
        {
            "purpose": "designs_download",
            "run_id": "run-a",
            "format": "json",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    with pytest.raises(DownloadTokenError, match="Invalid or expired"):
        verify_designs_download_token(token)


def test_assert_claims_match() -> None:
    claims = {"run_id": "run-a", "format": "tsv"}
    assert_designs_download_claims(claims, run_id="run-a", fmt="tsv")
    with pytest.raises(DownloadTokenError, match="run_ids"):
        assert_designs_download_claims(claims, run_id="run-b", fmt="tsv")
    with pytest.raises(DownloadTokenError, match="format"):
        assert_designs_download_claims(claims, run_id="run-a", fmt="json")
    with pytest.raises(DownloadTokenError, match="run_ids"):
        assert_designs_download_claims(claims, run_id=None, fmt="tsv")


def test_default_ttl_is_ten_minutes() -> None:
    assert DEFAULT_TTL_SECONDS == 600

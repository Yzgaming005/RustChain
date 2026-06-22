"""Regression test for the LIKE-wildcard hardening of /wallet/tx/<tx_hash>.

After the follow-up to PR #7551, the lookup endpoint rejects any
``tx_hash`` that is not exactly 32 hexadecimal characters (matching the
sibling ``/wallet/tx/<tx_hash>/status`` endpoint).

These tests guard against regression: a request shaped like
``/wallet/tx/%25`` (URL-encoded ``%``) or a hash containing the SQL
wildcard ``_`` must be rejected up-front with HTTP 400 — they must
never reach the immutable-ledger LIKE fallback.
"""

import sqlite3
import sys

import pytest

integrated_node = sys.modules["integrated_node"]

GOOD_HASH = "0123456789abcdef0123456789abcdef"
WILDCARD_HASH = "_______________________________"  # 31 underscores — bad length too
SHORT_HASH = "abc"
URL_ENCODED_PCT = "%25"  # literal "%" after URL decoding — a SQL wildcard


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "tx_lookup.db"
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE pending_ledger ("
            "ts INTEGER, from_miner TEXT, to_miner TEXT, amount_i64 INTEGER, "
            "reason TEXT, status TEXT, tx_hash TEXT, "
            "created_at INTEGER)"
        )
        # Seed a transfer reason so a wild match would otherwise succeed.
        db.execute(
            "INSERT INTO pending_ledger "
            "(ts, from_miner, to_miner, amount_i64, reason, status, "
            "tx_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1, "alice", "bob", 100,
                f"transfer_out:{GOOD_HASH}",
                "pending",
                GOOD_HASH,
                1,
            ),
        )
        db.commit()

    monkeypatch.setattr(
        integrated_node, "DB_PATH", str(db_path), raising=False
    )
    monkeypatch.setitem(
        integrated_node.api_wallet_tx_lookup.__globals__,
        "DB_PATH",
        str(db_path),
    )
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client


def test_wallet_tx_lookup_rejects_url_encoded_percent(client):
    """``%25`` is a SQL LIKE wildcard — must be rejected with 400."""
    response = client.get(f"/wallet/tx/{URL_ENCODED_PCT}")
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert "hexadecimal" in payload["error"]


def test_wallet_tx_lookup_rejects_underscore_wildcard(client):
    """``_`` is a SQL LIKE wildcard — must be rejected with 400."""
    response = client.get(f"/wallet/tx/{WILDCARD_HASH}")
    assert response.status_code == 400


def test_wallet_tx_lookup_rejects_short_hash(client):
    response = client.get(f"/wallet/tx/{SHORT_HASH}")
    assert response.status_code == 400


def test_wallet_tx_lookup_accepts_valid_hash_returns_pending(client):
    response = client.get(f"/wallet/tx/{GOOD_HASH}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["tx_hash"] == GOOD_HASH
    assert payload["status"] == "pending"


def test_wallet_tx_lookup_unknown_hash_returns_404(client):
    """Valid format but unknown hash → 404 (not 400)."""
    other = "ffffffffffffffffffffffffffffffff"
    response = client.get(f"/wallet/tx/{other}")
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["status"] == "not_found"
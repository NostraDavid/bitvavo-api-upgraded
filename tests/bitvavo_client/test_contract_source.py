# License notice from LICENSE.txt:
# Copyright (c) 2024, Bitvavo B.V.

"""The upstream drift check must fail on new contracts without contacting an exchange."""

from __future__ import annotations

import hashlib
import json
import socket
from typing import TYPE_CHECKING

import pytest

from scripts.check_bitvavo_contract import (
    CONTRACT_ROOT,
    contract_changes,
    fetch_document,
    latest_exchange_release,
    load_reviewed_manifest,
)

if TYPE_CHECKING:
    from pathlib import Path

RELEASE = "https://docs.bitvavo.com/releases/2026-08-07-exchange/"
REVIEWED = {
    "url": RELEASE,
    "title": "Exchange API",
    "tags": ["rest", "websocket"],
    "date_modified": "2026-08-07T00:00:00.000Z",
}


def feed(*items: dict) -> bytes:
    return json.dumps({"items": items}).encode()


def test_contract_pin() -> None:
    manifest = load_reviewed_manifest()
    snapshot = (CONTRACT_ROOT / manifest["schema"]).read_bytes()
    assert json.loads(snapshot)["info"]["version"] == manifest["openapi_info_version"]
    operations = {
        f"{method.upper()} {path}" for path, methods in json.loads(snapshot)["paths"].items() for method in methods
    }
    assert operations == manifest["rate_limit_weights"].keys()


def test_network_guard_blocks_connections_and_dns() -> None:
    with socket.socket() as connection, pytest.raises(pytest.fail.Exception, match="must mock network"):
        connection.connect(("127.0.0.1", 9))
    with pytest.raises(pytest.fail.Exception, match="must mock network"):
        socket.getaddrinfo("api.bitvavo.com", 443)


def test_reviewed_sources_match() -> None:
    schema = b"reviewed schema"
    manifest = {"source_sha256": hashlib.sha256(schema).hexdigest(), "latest_exchange_release": RELEASE}
    assert contract_changes(manifest, schema, feed(REVIEWED)) == []


def test_unreviewed_local_schema_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "schema.json").write_bytes(b"changed")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema": "schema.json", "schema_sha256": hashlib.sha256(b"reviewed").hexdigest()}),
    )
    monkeypatch.setattr("scripts.check_bitvavo_contract.CONTRACT_ROOT", tmp_path)
    with pytest.raises(ValueError, match="Local schema differs"):
        load_reviewed_manifest()


@pytest.mark.parametrize(
    "url",
    [
        "file:///nonexistent-bitvavo-fixture",
        "http://docs.bitvavo.com/api-specs/exchange-rest-api.yaml",
        "https://example.invalid/schema",
        "https://docs.bitvavo.com.invalid/schema",
    ],
)
def test_document_origin_is_restricted(url: str) -> None:
    with pytest.raises(ValueError, match="Documentation URLs must use"):
        fetch_document(url)


def test_changed_schema_requires_review() -> None:
    manifest = {"source_sha256": hashlib.sha256(b"reviewed schema").hexdigest(), "latest_exchange_release": RELEASE}
    changes = contract_changes(manifest, b"changed schema", feed(REVIEWED))
    assert len(changes) == 1
    assert changes[0].startswith("Upstream OpenAPI changed:")


def test_new_exchange_release_requires_review() -> None:
    schema = b"reviewed schema"
    manifest = {"source_sha256": hashlib.sha256(schema).hexdigest(), "latest_exchange_release": RELEASE}
    newer = "https://docs.bitvavo.com/releases/2026-12-01-exchange/"
    changes = contract_changes(
        manifest,
        schema,
        feed(REVIEWED, REVIEWED | {"url": newer, "date_modified": "2026-12-01T00:00:00.000Z"}),
    )
    assert changes == [f"Unreviewed Exchange API release: {newer}"]


def test_preview_and_other_apis_do_not_change_contract() -> None:
    assert (
        latest_exchange_release(
            feed(
                {
                    "url": "https://docs.bitvavo.com/releases/sneak-preview/",
                    "title": "Sneak preview",
                    "tags": ["sneak-preview"],
                    "date_modified": "2027-01-01T00:00:00Z",
                },
                {
                    "url": "https://docs.bitvavo.com/releases/2026-12-01-institutional/",
                    "title": "Institutional API",
                    "tags": ["institutional", "rest"],
                    "date_modified": "2026-12-01T00:00:00Z",
                },
                REVIEWED,
                REVIEWED
                | {"url": "https://docs.bitvavo.com/releases/v2.12.0/", "date_modified": "2025-09-28T00:00:00Z"},
            ),
        )
        == RELEASE
    )


def test_new_numbered_release_requires_review() -> None:
    schema = b"reviewed schema"
    manifest = {"source_sha256": hashlib.sha256(schema).hexdigest(), "latest_exchange_release": RELEASE}
    newer = "https://docs.bitvavo.com/releases/v2.13.0/"
    document = feed(REVIEWED, REVIEWED | {"url": newer, "date_modified": "2026-12-01T00:00:00Z"})
    assert contract_changes(manifest, schema, document) == [f"Unreviewed Exchange API release: {newer}"]


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"date_modified": None}, TypeError),
        ({"date_modified": "2026-08-07"}, ValueError),
        ({"url": "https://example.invalid/release"}, ValueError),
    ],
)
def test_unusable_exchange_metadata_requires_review(changes: dict, error: type[Exception]) -> None:
    with pytest.raises(error, match=r"timestamp|Unexpected Exchange"):
        latest_exchange_release(feed(REVIEWED | changes))


@pytest.mark.parametrize(
    ("document", "error", "message"),
    [
        (b"{}", TypeError, "Expected a JSON Feed"),
        (b'{"items": []}', ValueError, "No Exchange"),
        (b'{"items": "broken"}', TypeError, "Expected a JSON Feed"),
        (b"not json", json.JSONDecodeError, "Expecting value"),
    ],
)
def test_unusable_feed_does_not_silently_pass(document: bytes, error: type[Exception], message: str) -> None:
    with pytest.raises(error, match=message):
        latest_exchange_release(document)

#!/usr/bin/env python3
# License notice from LICENSE.txt:
# Copyright (c) 2024, Bitvavo B.V.

"""Report upstream Bitvavo schema or Exchange release changes without updating pins."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

CONTRACT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "bitvavo"
MAX_DOCUMENT_BYTES = 2_000_000


def fetch_document(url: str) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "docs.bitvavo.com":
        msg = "Documentation URLs must use https://docs.bitvavo.com"
        raise ValueError(msg)
    # The documentation CDN rejects urllib's default user agent.
    request = Request(  # noqa: S310 - HTTPS origin checked above
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; BitvavoContractCheck)"},
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310 - origin checked above
        content = response.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        msg = "Upstream document exceeds the size limit"
        raise ValueError(msg)
    return content


def latest_exchange_release(feed: bytes) -> str:
    document = json.loads(feed)
    if not isinstance(document, dict) or not isinstance(document.get("items"), list):
        msg = "Expected a JSON Feed with an items list"
        raise TypeError(msg)
    releases = []
    for item in document["items"]:
        if not isinstance(item, dict):
            continue
        tags = item.get("tags", [])
        if "sneak-preview" in tags:
            continue
        exchange = item.get("title") == "Exchange API" or ("rest" in tags and "institutional" not in tags)
        if not exchange:
            continue
        url = item["url"]
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "docs.bitvavo.com" or not parsed.path.startswith("/releases/"):
            msg = f"Unexpected Exchange release URL: {url}"
            raise ValueError(msg)
        timestamp = item.get("date_published") or item.get("date_modified")
        if not isinstance(timestamp, str):
            msg = f"Exchange release timestamp requires review: {url}"
            raise TypeError(msg)
        published = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if published.tzinfo is None:
            msg = "Exchange release timestamps must include a timezone"
            raise ValueError(msg)
        releases.append((published, url))
    if not releases:
        msg = "No Exchange API releases found in the upstream feed"
        raise ValueError(msg)
    return max(releases)[1]


def contract_changes(manifest: dict[str, Any], schema: bytes, feed: bytes) -> list[str]:
    changes = []
    # shortcut: prose edits also require review; add semantic diffs if these alerts become noisy.
    digest = hashlib.sha256(schema).hexdigest()
    if digest != manifest["source_sha256"]:
        changes.append(f"Upstream OpenAPI changed: expected {manifest['source_sha256']}, received {digest}")
    release = latest_exchange_release(feed)
    if release != manifest["latest_exchange_release"]:
        changes.append(f"Unreviewed Exchange API release: {release}")
    return changes


def load_reviewed_manifest() -> dict[str, Any]:
    manifest = json.loads((CONTRACT_ROOT / "manifest.json").read_text())
    snapshot = (CONTRACT_ROOT / manifest["schema"]).read_bytes()
    if hashlib.sha256(snapshot).hexdigest() != manifest["schema_sha256"]:
        msg = "Local schema differs from the reviewed snapshot"
        raise ValueError(msg)
    return manifest


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        manifest = load_reviewed_manifest()
        changes = contract_changes(
            manifest,
            fetch_document(manifest["source_url"]),
            fetch_document(manifest["releases_url"]),
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Bitvavo contract check failed: {error}", file=sys.stderr)
        return 1
    if changes:
        print("\n".join(changes), file=sys.stderr)
        print("Review the release notes, update the versioned contract and run just check.", file=sys.stderr)
        return 1
    print(f"Bitvavo {manifest['contract_version']}: upstream schema and Exchange release match the reviewed contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

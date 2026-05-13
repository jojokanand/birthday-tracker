r"""One-shot backfill of the lowercase mirror fields on ``contacts`` documents.

Run once after deploying the change that introduced ``full_name_lower``,
``preferred_name_lower``, and ``email_lower`` on :class:`Contact` so existing
documents written before that change pick up the new fields.

Idempotent: re-running re-derives the lowercase values and writes them back,
which is a no-op for any document that has already been backfilled.

Usage::

    # against the live project
    GOOGLE_CLOUD_PROJECT=birthday-tracker-496115 \\
        uv run python -m scripts.backfill_contact_lowercase

    # against the local emulator
    FIRESTORE_EMULATOR_HOST=localhost:8085 \\
        GOOGLE_CLOUD_PROJECT=demo-project \\
        uv run python -m scripts.backfill_contact_lowercase
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from birthday_tracker.adapters import build_async_client
from birthday_tracker.adapters.firestore import CONTACTS_COLLECTION
from birthday_tracker.models import Contact


async def backfill(*, project_id: str, collection: str, dry_run: bool) -> tuple[int, int]:
    """Walk the contacts collection and rewrite each document.

    Args:
        project_id: GCP project to talk to (or ``demo-project`` against
            the emulator).
        collection: Firestore collection name. Default matches the live app.
        dry_run: If ``True``, log what would change but don't write anything.

    Returns:
        ``(scanned, written)``. ``written`` is always 0 in dry-run mode.
    """
    client = build_async_client(project_id=project_id)
    scanned = 0
    written = 0
    async for snapshot in client.collection(collection).stream():
        scanned += 1
        data = snapshot.to_dict()
        if data is None:
            continue
        # ``Contact.model_validate`` re-runs the validators, which sets
        # the lowercase mirror fields from the source values. Dumping
        # back as JSON-mode primitives gives the exact wire-format the
        # adapter writes during normal operation.
        contact = Contact.model_validate(data)
        payload = contact.model_dump(mode="json")
        existing_lowers = (
            data.get("full_name_lower"),
            data.get("preferred_name_lower"),
            data.get("email_lower"),
        )
        new_lowers = (
            payload["full_name_lower"],
            payload["preferred_name_lower"],
            payload["email_lower"],
        )
        if existing_lowers == new_lowers:
            continue
        if dry_run:
            print(
                f"[dry-run] would update {snapshot.id}: {existing_lowers!r} -> {new_lowers!r}",
                file=sys.stderr,
            )
        else:
            await client.collection(collection).document(snapshot.id).set(payload)
        written += 1 if not dry_run else 0
    return (scanned, written)


def main() -> int:
    """CLI entry point.

    Returns:
        Process exit code (0 on success, 1 on missing project id).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-id",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        help="GCP project id (or set GOOGLE_CLOUD_PROJECT).",
    )
    parser.add_argument(
        "--collection",
        default=CONTACTS_COLLECTION,
        help=f"Firestore collection name (default: {CONTACTS_COLLECTION!r}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log changes without writing.",
    )
    args = parser.parse_args()

    if not args.project_id:
        print(
            "error: --project-id is required (or set GOOGLE_CLOUD_PROJECT)",
            file=sys.stderr,
        )
        return 1

    scanned, written = asyncio.run(
        backfill(
            project_id=args.project_id,
            collection=args.collection,
            dry_run=args.dry_run,
        )
    )
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"scanned={scanned} updated={written}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

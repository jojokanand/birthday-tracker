"""Adapters wrapping external systems (Firestore, Twilio, Gmail API)."""

from birthday_tracker.adapters.firestore import (
    CONTACTS_COLLECTION,
    FirestoreContactRepository,
    build_async_client,
)
from birthday_tracker.adapters.in_memory import InMemoryContactRepository

__all__ = [
    "CONTACTS_COLLECTION",
    "FirestoreContactRepository",
    "InMemoryContactRepository",
    "build_async_client",
]

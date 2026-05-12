"""Adapters wrapping external systems (Firestore, Twilio, Gmail API)."""

from birthday_tracker.adapters.firestore import (
    COLLECTION_REQUESTS_COLLECTION,
    CONTACTS_COLLECTION,
    FirestoreCollectionRequestRepository,
    FirestoreContactRepository,
    build_async_client,
)
from birthday_tracker.adapters.gmail import (
    GMAIL_SCOPES,
    GmailNotifier,
    build_gmail_service,
    load_gmail_credentials,
)
from birthday_tracker.adapters.in_memory import (
    InMemoryCollectionRequestRepository,
    InMemoryContactRepository,
)
from birthday_tracker.adapters.twilio import TwilioNotifier, build_twilio_client

__all__ = [
    "COLLECTION_REQUESTS_COLLECTION",
    "CONTACTS_COLLECTION",
    "GMAIL_SCOPES",
    "FirestoreCollectionRequestRepository",
    "FirestoreContactRepository",
    "GmailNotifier",
    "InMemoryCollectionRequestRepository",
    "InMemoryContactRepository",
    "TwilioNotifier",
    "build_async_client",
    "build_gmail_service",
    "build_twilio_client",
    "load_gmail_credentials",
]

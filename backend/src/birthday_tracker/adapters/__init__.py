"""Adapters wrapping external systems (Firestore, Twilio, Gmail API)."""

from birthday_tracker.adapters.firestore import (
    CONTACTS_COLLECTION,
    FirestoreContactRepository,
    build_async_client,
)
from birthday_tracker.adapters.gmail import (
    GMAIL_SCOPES,
    GmailNotifier,
    build_gmail_service,
    load_gmail_credentials,
)
from birthday_tracker.adapters.in_memory import InMemoryContactRepository
from birthday_tracker.adapters.twilio import TwilioNotifier, build_twilio_client

__all__ = [
    "CONTACTS_COLLECTION",
    "GMAIL_SCOPES",
    "FirestoreContactRepository",
    "GmailNotifier",
    "InMemoryContactRepository",
    "TwilioNotifier",
    "build_async_client",
    "build_gmail_service",
    "build_twilio_client",
    "load_gmail_credentials",
]

"""Business-logic services. Stateless; depend on adapters via constructor injection."""

from birthday_tracker.services.repositories import ContactRepository

__all__ = ["ContactRepository"]

birthday_tracker
================

.. automodule:: birthday_tracker
   :members:

Configuration
-------------

.. autopydantic_settings:: birthday_tracker.core.config.Settings
   :settings-show-json: False
   :settings-show-config-summary: False

.. autoclass:: birthday_tracker.core.config.AppEnv
   :members:
   :undoc-members:
   :show-inheritance:

.. autofunction:: birthday_tracker.core.config.get_settings

Logging
-------

.. automodule:: birthday_tracker.core.logging
   :members:

Readiness checks
----------------

.. automodule:: birthday_tracker.core.health
   :members:
   :exclude-members: ReadinessResult

.. autoclass:: birthday_tracker.core.health.ReadinessResult
   :members:
   :show-inheritance:
   :no-index:

HTTP API
--------

.. automodule:: birthday_tracker.main
   :members:

Health endpoint
~~~~~~~~~~~~~~~

.. autofunction:: birthday_tracker.api.health.get_health

.. autopydantic_model:: birthday_tracker.api.health.HealthResponse
   :model-show-json: False
   :model-show-config-summary: False

Readiness endpoint
~~~~~~~~~~~~~~~~~~

.. autofunction:: birthday_tracker.api.ready.get_ready

.. autopydantic_model:: birthday_tracker.api.ready.ReadinessResponse
   :model-show-json: False
   :model-show-config-summary: False

Errors (RFC 7807)
~~~~~~~~~~~~~~~~~

.. automodule:: birthday_tracker.api.errors
   :members:
   :exclude-members: ProblemDetail

.. autopydantic_model:: birthday_tracker.api.errors.ProblemDetail
   :model-show-json: False
   :model-show-config-summary: False

Domain models
-------------

.. autopydantic_model:: birthday_tracker.models.address.Address
   :model-show-json: False
   :model-show-config-summary: False

.. autopydantic_model:: birthday_tracker.models.birthday.Birthday
   :model-show-json: False
   :model-show-config-summary: False

.. autopydantic_model:: birthday_tracker.models.contact.Contact
   :model-show-json: False
   :model-show-config-summary: False

.. autopydantic_model:: birthday_tracker.models.collection_request.CollectionRequest
   :model-show-json: False
   :model-show-config-summary: False

.. autoclass:: birthday_tracker.models.collection_request.Channel
   :members:
   :undoc-members:
   :show-inheritance:

Token primitives
----------------

.. autofunction:: birthday_tracker.core.tokens.sign_token

.. autofunction:: birthday_tracker.core.tokens.verify_token

.. autofunction:: birthday_tracker.core.tokens.hash_token

.. autoclass:: birthday_tracker.core.tokens.TokenPayload
   :members:
   :show-inheritance:
   :no-index:

.. autoexception:: birthday_tracker.core.tokens.TokenInvalid
   :show-inheritance:

.. autoexception:: birthday_tracker.core.tokens.TokenExpired
   :show-inheritance:

Rate limiter
------------

.. autoclass:: birthday_tracker.core.rate_limit.RateLimiter
   :members:
   :show-inheritance:

.. autoexception:: birthday_tracker.core.rate_limit.RateLimitExceeded
   :show-inheritance:

Services layer (Protocols)
--------------------------

.. automodule:: birthday_tracker.services
   :members:

.. autoclass:: birthday_tracker.services.repositories.ContactRepository
   :members:
   :show-inheritance:
   :no-index:

.. autoclass:: birthday_tracker.services.repositories.CollectionRequestRepository
   :members:
   :show-inheritance:
   :no-index:

.. autoclass:: birthday_tracker.services.notifiers.SmsNotifier
   :members:
   :show-inheritance:
   :no-index:

.. autoclass:: birthday_tracker.services.notifiers.EmailNotifier
   :members:
   :show-inheritance:
   :no-index:

.. autoexception:: birthday_tracker.services.notifiers.NotificationError
   :show-inheritance:
   :no-index:

Collection request service
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: birthday_tracker.services.collection_requests.CollectionRequestService
   :members:
   :show-inheritance:

.. autoclass:: birthday_tracker.services.collection_requests.IssuedRequest
   :members:
   :show-inheritance:
   :no-index:

.. autoclass:: birthday_tracker.services.collection_requests.FormSubmission
   :members:
   :show-inheritance:
   :no-index:

.. autoexception:: birthday_tracker.services.collection_requests.ContactNotFound
   :show-inheritance:

.. autoexception:: birthday_tracker.services.collection_requests.RequestNotPending
   :show-inheritance:

Contacts endpoint
~~~~~~~~~~~~~~~~~

.. autofunction:: birthday_tracker.api.contacts.list_contacts

.. autofunction:: birthday_tracker.api.contacts.create_contact

.. autofunction:: birthday_tracker.api.contacts.get_contact

.. autofunction:: birthday_tracker.api.contacts.update_contact

.. autofunction:: birthday_tracker.api.contacts.delete_contact

.. autopydantic_model:: birthday_tracker.api.contacts.CreateContactBody
   :model-show-json: False
   :model-show-config-summary: False

.. autopydantic_model:: birthday_tracker.api.contacts.UpdateContactBody
   :model-show-json: False
   :model-show-config-summary: False

.. autopydantic_model:: birthday_tracker.api.contacts.ContactResponse
   :model-show-json: False
   :model-show-config-summary: False

Collection-requests endpoint
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: birthday_tracker.api.collection_requests.issue_collection_request

.. autopydantic_model:: birthday_tracker.api.collection_requests.IssueRequestBody
   :model-show-json: False
   :model-show-config-summary: False

.. autopydantic_model:: birthday_tracker.api.collection_requests.IssuedRequestResponse
   :model-show-json: False
   :model-show-config-summary: False

Form endpoints
~~~~~~~~~~~~~~

.. autofunction:: birthday_tracker.api.form.get_form_metadata

.. autofunction:: birthday_tracker.api.form.submit_form

.. autopydantic_model:: birthday_tracker.api.form.FormMetadataResponse
   :model-show-json: False
   :model-show-config-summary: False

.. autopydantic_model:: birthday_tracker.api.form.FormSubmissionBody
   :model-show-json: False
   :model-show-config-summary: False

Adapters
--------

.. automodule:: birthday_tracker.adapters
   :members:
   :exclude-members: InMemoryContactRepository, InMemoryCollectionRequestRepository, FirestoreContactRepository, FirestoreCollectionRequestRepository, TwilioNotifier, GmailNotifier

.. autoclass:: birthday_tracker.adapters.in_memory.InMemoryContactRepository
   :members:
   :show-inheritance:

.. autoclass:: birthday_tracker.adapters.in_memory.InMemoryCollectionRequestRepository
   :members:
   :show-inheritance:

.. autoclass:: birthday_tracker.adapters.firestore.FirestoreContactRepository
   :members:
   :show-inheritance:

.. autoclass:: birthday_tracker.adapters.firestore.FirestoreCollectionRequestRepository
   :members:
   :show-inheritance:

.. autofunction:: birthday_tracker.adapters.firestore.build_async_client

.. autoclass:: birthday_tracker.adapters.twilio.TwilioNotifier
   :members:
   :show-inheritance:

.. autofunction:: birthday_tracker.adapters.twilio.build_twilio_client

.. autoclass:: birthday_tracker.adapters.gmail.GmailNotifier
   :members:
   :show-inheritance:

.. autofunction:: birthday_tracker.adapters.gmail.load_gmail_credentials

.. autofunction:: birthday_tracker.adapters.gmail.build_gmail_service

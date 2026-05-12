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

Repositories (services layer)
-----------------------------

.. automodule:: birthday_tracker.services
   :members:

.. autoclass:: birthday_tracker.services.repositories.ContactRepository
   :members:
   :show-inheritance:
   :no-index:

Adapters
--------

.. automodule:: birthday_tracker.adapters
   :members:
   :exclude-members: InMemoryContactRepository, FirestoreContactRepository

.. autoclass:: birthday_tracker.adapters.in_memory.InMemoryContactRepository
   :members:
   :show-inheritance:

.. autoclass:: birthday_tracker.adapters.firestore.FirestoreContactRepository
   :members:
   :show-inheritance:

.. autofunction:: birthday_tracker.adapters.firestore.build_async_client

Data Models
===========

ORM Models
----------

SQLAlchemy declarative models that define the database schema.

.. automodule:: src.database.models
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: metadata, registry

Database Session
----------------

Async session management and the FastAPI ``get_db`` dependency.

.. automodule:: src.database.db
   :members:
   :undoc-members:
   :show-inheritance:

Pydantic Schemas
----------------

Request/response schemas used for data validation and serialisation
across the API layer.

.. automodule:: src.schemas
   :members:
   :undoc-members:
   :show-inheritance:

Services
========

Application services encapsulate business logic and external integrations,
keeping the API layer thin.

Authentication & Tokens
-----------------------

JWT creation/validation, password hashing, and FastAPI authentication
dependencies.

.. automodule:: src.services.auth
   :members:
   :undoc-members:
   :show-inheritance:

User Workflows
--------------

Orchestrates user repository and avatar resolution.

.. automodule:: src.services.users
   :members:
   :undoc-members:
   :show-inheritance:

Redis Caching
-------------

Caching layer for the authenticated user to reduce database queries
during token validation.

.. automodule:: src.services.cache
   :members:
   :undoc-members:
   :show-inheritance:

Email
-----

Transactional emails for verification and password reset.

.. automodule:: src.services.email
   :members:
   :undoc-members:
   :show-inheritance:

Avatar
------

Default avatar resolution via Gravatar.

.. automodule:: src.services.avatar
   :members:
   :undoc-members:
   :show-inheritance:

File Upload
-----------

Cloudinary upload adapter for user avatars.

.. automodule:: src.services.upload_file
   :members:
   :undoc-members:
   :show-inheritance:

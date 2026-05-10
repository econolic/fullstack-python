Contacts Final REST API
=======================

**Contacts REST API** is a FastAPI-based application for managing personal
contacts with JWT authentication, email verification, Redis caching, and
role-based access control.

Key features:

* CRUD operations for contacts scoped to the authenticated user.
* JWT ``access_token`` / ``refresh_token`` pair with rotation and revocation.
* Email verification and password-reset workflows.
* Redis caching of the current user to reduce database load.
* Role-based access: ``user`` and ``admin`` roles.
* Cloudinary avatar uploads (admin-only).
* Sphinx auto-generated API reference from source docstrings.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api
   services
   repository
   models
   configuration


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

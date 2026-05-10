API Routers
===========

FastAPI routers that define the HTTP endpoints.  Each router is mounted
under the ``/api`` prefix in :mod:`main`.

Authentication
--------------

Registration, login, JWT token management, email verification and
password reset.

``POST /api/auth/register`` returns ``201 Created`` or ``409 Conflict`` for
duplicate username/email.  Login, refresh, and logout use bearer-token style
credentials and return ``401 Unauthorized`` when credentials or refresh tokens
are invalid.

Password reset endpoints intentionally return a generic ``200 OK`` for the
request step to avoid email enumeration; confirmation returns ``400 Bad
Request`` for invalid, expired, or already used reset tokens.

.. automodule:: src.api.auth
   :members:
   :undoc-members:
   :show-inheritance:

Users
-----

Current user profile and avatar management.

``GET /api/users/me`` requires a valid access token and is rate limited to
10 requests per minute, returning ``429 Too Many Requests`` when exceeded.
``PATCH /api/users/avatar`` requires an authenticated ``admin`` user and
returns ``403 Forbidden`` for ordinary users.

.. automodule:: src.api.users
   :members:
   :undoc-members:
   :show-inheritance:

Contacts
--------

Protected CRUD operations for contacts owned by the authenticated user.

All contact endpoints require a bearer access token and are scoped to the
current user.  Create returns ``201 Created``, delete returns ``204 No
Content``, missing or cross-user contacts return ``404 Not Found``, and
duplicate per-user emails return ``409 Conflict``.

.. automodule:: src.api.contacts
   :members:
   :undoc-members:
   :show-inheritance:

Utilities
---------

Health checks and service diagnostics.

``GET /api/utils/healthchecker`` is public and returns ``200 OK`` when the
database check succeeds or ``500 Internal Server Error`` when dependencies are
unavailable.

.. automodule:: src.api.utils
   :members:
   :undoc-members:
   :show-inheritance:

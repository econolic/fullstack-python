from libgravatar import Gravatar


class AvatarService:
    """Resolve default avatar URLs for new users via Gravatar."""

    def get_default_avatar(self, email: str) -> str | None:
        """Return a Gravatar URL for *email*, or ``None`` on failure.

        :param email: The user's email address.
        :type email: str
        :returns: A Gravatar image URL or ``None`` if the lookup fails.
        :rtype: str | None
        """
        try:
            return Gravatar(email).get_image()
        except Exception:
            return None

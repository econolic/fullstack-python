import os
import sys

sys.path.insert(0, os.path.abspath(".."))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./docs.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("JWT_SECRET", "docs-secret")
os.environ.setdefault("MAIL_USERNAME", "docs@example.com")
os.environ.setdefault("MAIL_PASSWORD", "password")
os.environ.setdefault("MAIL_FROM", "docs@example.com")
os.environ.setdefault("MAIL_SERVER", "smtp.example.com")
os.environ.setdefault("CLD_NAME", "cloud")
os.environ.setdefault("CLD_API_KEY", "key")
os.environ.setdefault("CLD_API_SECRET", "secret")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_SECONDS", "3600")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_SECONDS", "604800")
os.environ.setdefault("PASSWORD_RESET_TOKEN_EXPIRE_SECONDS", "3600")
os.environ.setdefault("USER_CACHE_TTL_SECONDS", "900")

project = "Contacts Final REST API"
author = "Max"

extensions = ["sphinx.ext.autodoc"]
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "nature"

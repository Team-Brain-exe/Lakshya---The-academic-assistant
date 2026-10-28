"""Unit tests never touch a database, but the route modules import the app config,
which insists on these two variables. Harmless placeholders, only set if missing."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@localhost:5432/unused")
os.environ.setdefault("SESSION_SECRET", "unit-test-secret")

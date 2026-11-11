#!/bin/sh
# Apply any pending Alembic migrations before the app starts, in every
# environment. This replaces the old create_all()-on-boot approach, which
# could only create missing tables -- it silently no-oped on changes to an
# existing DB (e.g. a new enum value), so drift between models.py and the
# live schema went unnoticed until a request hit it at runtime.
set -e

alembic upgrade head

exec "$@"

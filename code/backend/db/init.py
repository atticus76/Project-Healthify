"""Create Healthify's tables in the database named by DATABASE_URL.

Run from the `code/` folder:

    python -m backend.db.init

Safe to run again: tables that already exist are left alone.
"""

from __future__ import annotations

import sys

from backend.db import DatabaseError, MissingDatabaseURL, create_schema


def main() -> int:
    try:
        create_schema()
    except MissingDatabaseURL as exc:
        print(exc, file=sys.stderr)
        return 1
    except DatabaseError as exc:
        print(f"{exc} (Is the Supabase project paused? Is DATABASE_URL right?)", file=sys.stderr)
        if exc.__cause__ is not None:
            print(f"Details: {exc.__cause__}", file=sys.stderr)
        return 1
    print("Schema is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

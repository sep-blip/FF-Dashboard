from __future__ import annotations

from .repository import connect_database, initialize_schema


def main() -> None:
    with connect_database() as connection:
        initialize_schema(connection)
    print("Database schema initialized.")


if __name__ == "__main__":
    main()

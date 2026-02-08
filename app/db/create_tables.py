from __future__ import annotations

from app.db import init_db


def main() -> None:
    init_db()
    print("Tables created.")


if __name__ == "__main__":
    main()

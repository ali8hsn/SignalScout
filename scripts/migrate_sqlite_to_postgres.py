"""Copy every table row-for-row from the local SQLite DB into Postgres.

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/db python scripts/migrate_sqlite_to_postgres.py
    python scripts/migrate_sqlite_to_postgres.py --dry-run   # no Postgres needed; prints table/row counts

Tables are discovered dynamically from sqlite_master, so tables added by later
phases (subscribers, enrichment_cache, ...) are migrated automatically.
Idempotent: each run truncates all destination tables in one transaction, copies
all rows, verifies counts, and commits only if the complete migration succeeds.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db.database import Database

try:  # required for the actual migration, not for --dry-run
    import psycopg
    from psycopg import sql
except ImportError:
    psycopg = None  # type: ignore[assignment]
    sql = None  # type: ignore[assignment]

BATCH_SIZE = 500
ROOT_DIR = Path(__file__).resolve().parent.parent


def sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def row_count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def dependency_order(conn: sqlite3.Connection, tables: list[str]) -> list[str]:
    """Topologically sort tables so foreign-key parents are copied before children."""
    deps: dict[str, set[str]] = {}
    for table in tables:
        fk_rows = conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
        deps[table] = {r[2] for r in fk_rows if r[2] in tables and r[2] != table}
    ordered: list[str] = []
    remaining = set(tables)
    while remaining:
        ready = sorted(t for t in remaining if deps[t] <= set(ordered))
        if not ready:  # FK cycle: fall back to remaining alphabetical order
            ready = sorted(remaining)
        ordered.extend(ready)
        remaining -= set(ready)
    return ordered


def dry_run(sqlite_conn: sqlite3.Connection) -> None:
    tables = sqlite_tables(sqlite_conn)
    print(f"[dry-run] {len(tables)} table(s) would be migrated:")
    total = 0
    for table in tables:
        count = row_count(sqlite_conn, table)
        total += count
        print(f"  {table:<24} {count:>6} rows")
    print(f"  {'TOTAL':<24} {total:>6} rows")


def ensure_table(pg_conn: "psycopg.Connection", sqlite_conn: sqlite3.Connection, table: str) -> None:
    """Make sure `table` exists in Postgres. schema.sql should have created it;
    as a fallback, replay the (mostly portable TEXT/REAL/INTEGER) SQLite DDL."""
    exists = pg_conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    ).fetchone()
    if exists:
        return
    ddl = sqlite_conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()[0]
    try:
        pg_conn.execute(ddl)
        print(f"  [warn] {table}: not in schema.sql, created from SQLite DDL")
    except psycopg.Error as exc:
        raise RuntimeError(
            f"{table}: missing in Postgres and its SQLite DDL is not portable: {exc}"
        ) from exc


def truncate_tables(pg_conn: "psycopg.Connection", tables: list[str]) -> None:
    """Empty the complete destination set at once so CASCADE cannot erase rows copied earlier."""
    if not tables:
        return
    identifiers = sql.SQL(", ").join(sql.Identifier(table) for table in tables)
    pg_conn.execute(sql.SQL("TRUNCATE TABLE {} CASCADE").format(identifiers))


def copy_table(pg_conn: "psycopg.Connection", sqlite_conn: sqlite3.Connection, table: str) -> int:
    cur = sqlite_conn.execute(f'SELECT * FROM "{table}"')
    columns = [d[0] for d in cur.description]
    insert_sql = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )

    copied = 0
    with pg_conn.cursor() as pg_cur:
        while True:
            batch = cur.fetchmany(BATCH_SIZE)
            if not batch:
                break
            # Per-row execute (not executemany): avoids psycopg pipeline mode,
            # which some Postgres flavors don't support; row counts here are small.
            for row in batch:
                pg_cur.execute(insert_sql, tuple(row))
            copied += len(batch)
    return copied


def verify_table(pg_conn: "psycopg.Connection", table: str, expected: int) -> None:
    actual = pg_conn.execute(
        sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
    ).fetchone()[0]
    if actual != expected:
        raise RuntimeError(f"{table}: expected {expected} rows after copy, found {actual}")


def migrate(sqlite_conn: sqlite3.Connection, database_url: str) -> None:
    if psycopg is None:
        raise SystemExit("psycopg is not installed. Run: pip install 'psycopg[binary]>=3.1'")

    db = Database(Path(":memory:"), database_url=database_url)
    db.init_schema()  # create all schema.sql tables in Postgres first
    db.close()

    with psycopg.connect(database_url) as pg_conn:
        total = 0
        tables = dependency_order(sqlite_conn, sqlite_tables(sqlite_conn))
        for table in tables:
            ensure_table(pg_conn, sqlite_conn, table)
        truncate_tables(pg_conn, tables)
        for table in tables:
            copied = copy_table(pg_conn, sqlite_conn, table)
            verify_table(pg_conn, table, copied)
            total += copied
            print(f"  {table:<24} {copied:>6} rows copied")
        pg_conn.commit()
    print(f"Done: {total} rows migrated to Postgres.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, default=None, help="path to the SQLite DB (default: settings)")
    parser.add_argument("--dry-run", action="store_true", help="print table/row counts without touching Postgres")
    args = parser.parse_args()

    sqlite_path = args.sqlite or Path(
        os.environ.get("SIGNAL_SCOUT_DB", ROOT_DIR / "signal_scout.db")
    )
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite DB not found: {sqlite_path}")
    with sqlite3.connect(sqlite_path) as sqlite_conn:
        if args.dry_run:
            dry_run(sqlite_conn)
            return

        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url:
            raise SystemExit("DATABASE_URL is not set (use --dry-run to preview without Postgres)")
        migrate(sqlite_conn, database_url)


if __name__ == "__main__":
    main()

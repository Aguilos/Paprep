from pathlib import Path

from sqlalchemy import create_engine, select, text

from app import db
import models  # noqa: F401
from config import get_database_uri


SOURCE_DB = Path(__file__).resolve().with_name('paprep.db')
BATCH_SIZE = 500


def chunked(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def get_destination_uri():
    destination_uri = get_database_uri()
    if destination_uri.startswith('sqlite'):
        raise SystemExit('DATABASE_URL must point to PostgreSQL/Supabase before migrating data.')
    return destination_uri


def copy_table(source_connection, destination_connection, table):
    rows = source_connection.execute(select(table)).mappings().all()
    if not rows:
        return 0

    payload = [dict(row) for row in rows]
    for batch in chunked(payload, BATCH_SIZE):
        destination_connection.execute(table.insert(), batch)
    return len(payload)


def clear_destination_tables(destination_connection):
    table_list = ', '.join(table.name for table in db.metadata.sorted_tables)
    destination_connection.execute(
        text(f'TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE')
    )


def reset_sequence(destination_connection, table):
    if destination_connection.dialect.name != 'postgresql':
        return

    primary_key_columns = list(table.primary_key.columns)
    if len(primary_key_columns) != 1 or primary_key_columns[0].name != 'id':
        return

    max_id = destination_connection.execute(
        text(f'SELECT MAX(id) FROM {table.name}')
    ).scalar_one()

    if max_id is None:
        destination_connection.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), 1, false)"
            )
        )
    else:
        destination_connection.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), :max_id, true)"
            ),
            {'max_id': max_id},
        )


def main():
    if not SOURCE_DB.exists():
        raise SystemExit(f'Source SQLite database not found: {SOURCE_DB}')

    destination_uri = get_destination_uri()
    source_engine = create_engine(f'sqlite:///{SOURCE_DB}')
    destination_engine = create_engine(destination_uri)

    db.metadata.create_all(destination_engine)

    totals = {}
    with source_engine.begin() as source_connection, destination_engine.begin() as destination_connection:
        clear_destination_tables(destination_connection)
        for table in db.metadata.sorted_tables:
            copied = copy_table(source_connection, destination_connection, table)
            totals[table.name] = copied
            reset_sequence(destination_connection, table)

    for table_name, copied in totals.items():
        print(f'{table_name}: {copied} rows copied')

    print('Migration complete.')


if __name__ == '__main__':
    main()
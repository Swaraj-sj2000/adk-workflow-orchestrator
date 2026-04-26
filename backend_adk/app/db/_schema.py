from sqlalchemy import inspect, text


ADDITIVE_COLUMNS = {
    "tenants": {
        "logo_url": "TEXT",
        "description": "TEXT",
        "industry": "VARCHAR",
        "website_url": "TEXT",
        "headquarters": "VARCHAR",
        "employee_count_range": "VARCHAR",
        "founded_year": "INTEGER",
        "contact_email": "VARCHAR",
        "contact_phone": "VARCHAR",
    },
    "users": {
        "tenant_id": "INTEGER",
        "password_reset_token": "VARCHAR",
        "password_reset_expires": "DATETIME",
        "email_verified": "INTEGER DEFAULT 1",
        "email_verify_token": "VARCHAR",
        "totp_secret": "VARCHAR",
        "totp_enabled": "INTEGER DEFAULT 0",
        "deleted_at": "DATETIME",
        # Extended profile
        "first_name": "VARCHAR",
        "last_name": "VARCHAR",
        "phone": "VARCHAR",
        "secondary_email": "VARCHAR",
        "position": "VARCHAR",
        "location": "VARCHAR",
        "avatar_url": "TEXT",
    },
    "projects": {
        "tenant_id": "INTEGER",
        "deleted_at": "DATETIME",
    },
    "tasks": {
        "tenant_id": "INTEGER",
        "deleted_at": "DATETIME",
    },
    "employee_profiles": {
        "tenant_id": "INTEGER",
        "duty_start_hour": "FLOAT",
        "duty_end_hour": "FLOAT",
        "deleted_at": "DATETIME",
    },
    "client_profiles": {
        "tenant_id": "INTEGER",
    },
    "user_preferences": {
        "google_calendar_connected": "INTEGER DEFAULT 0",
        "google_calendar_token": "TEXT",
        "google_calendar_email": "VARCHAR",
        "onboarding_complete": "INTEGER DEFAULT 0",
        "currency": "VARCHAR DEFAULT 'USD'",
    },
    "tenant_settings": {
        "max_teams": "INTEGER DEFAULT 1",
        "subscription_expires_at": "DATETIME",
    },
}


_ALLOWED_TABLES = frozenset(ADDITIVE_COLUMNS.keys())
_ALLOWED_COLUMNS: frozenset[str] = frozenset(
    col for cols in ADDITIVE_COLUMNS.values() for col in cols
)

# Tables and columns that must be made nullable (SQLite table-recreation technique)
_MAKE_NULLABLE = [
    ("teams", "project_id"),
]


def _drop_not_null(connection, table_name: str, column_name: str) -> None:
    """Recreate a SQLite table to remove NOT NULL from one column."""
    result = connection.execute(text(f"PRAGMA table_info(\"{table_name}\")"))
    cols = result.fetchall()  # (cid, name, type, notnull, dflt_value, pk)

    target = next((c for c in cols if c[1] == column_name), None)
    if target is None or target[3] == 0:
        return  # already nullable or column absent

    col_defs = []
    for col in cols:
        cid, name, ctype, notnull, dflt_value, pk = col
        parts = [f'"{name}"', ctype or "TEXT"]
        if pk:
            parts.append("PRIMARY KEY")
        if notnull and name != column_name:
            parts.append("NOT NULL")
        if dflt_value is not None:
            parts.append(f"DEFAULT {dflt_value}")
        col_defs.append(" ".join(parts))

    col_names = ", ".join(f'"{c[1]}"' for c in cols)
    backup = f'_{table_name}_nb_bkp'

    connection.execute(text(f'ALTER TABLE "{table_name}" RENAME TO "{backup}"'))
    connection.execute(text(f'CREATE TABLE "{table_name}" ({", ".join(col_defs)})'))
    connection.execute(text(f'INSERT INTO "{table_name}" SELECT {col_names} FROM "{backup}"'))
    connection.execute(text(f'DROP TABLE "{backup}"'))


def ensure_runtime_schema(engine) -> None:
    inspector = inspect(engine)

    with engine.begin() as connection:
        # 1. Additive column migrations
        for table_name, columns in ADDITIVE_COLUMNS.items():
            assert table_name in _ALLOWED_TABLES, f"Unexpected table: {table_name}"
            if table_name not in inspector.get_table_names():
                continue

            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                assert column_name in _ALLOWED_COLUMNS, f"Unexpected column: {column_name}"
                if column_name in existing_columns:
                    continue
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))

        # 2. Drop NOT NULL constraints where required
        existing_tables = set(inspector.get_table_names())
        for table_name, column_name in _MAKE_NULLABLE:
            if table_name in existing_tables:
                _drop_not_null(connection, table_name, column_name)

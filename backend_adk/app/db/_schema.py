from sqlalchemy import inspect, text


ADDITIVE_COLUMNS = {
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


def ensure_runtime_schema(engine) -> None:
    inspector = inspect(engine)

    with engine.begin() as connection:
        for table_name, columns in ADDITIVE_COLUMNS.items():
            # Explicit allowlist — guards against injection if ADDITIVE_COLUMNS is ever
            # extended with values from non-hardcoded sources.
            assert table_name in _ALLOWED_TABLES, f"Unexpected table: {table_name}"
            if table_name not in inspector.get_table_names():
                continue

            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                assert column_name in _ALLOWED_COLUMNS, f"Unexpected column: {column_name}"
                if column_name in existing_columns:
                    continue
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))

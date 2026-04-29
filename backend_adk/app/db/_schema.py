from sqlalchemy import inspect, text


def _ts(engine) -> str:
    """Return the correct timestamp type for the current dialect."""
    return "TIMESTAMP" if engine.dialect.name == "postgresql" else "DATETIME"


def _additive_columns(engine):
    ts = _ts(engine)
    is_pg = engine.dialect.name == "postgresql"
    return {
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
            "password_reset_expires": ts,
            "email_verified": "BOOLEAN DEFAULT TRUE" if is_pg else "INTEGER DEFAULT 1",
            "email_verify_token": "VARCHAR",
            "totp_secret": "VARCHAR",
            "totp_enabled": "BOOLEAN DEFAULT FALSE" if is_pg else "INTEGER DEFAULT 0",
            "deleted_at": ts,
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
            "deleted_at": ts,
        },
        "tasks": {
            "tenant_id": "INTEGER",
            "deleted_at": ts,
        },
        "employee_profiles": {
            "tenant_id": "INTEGER",
            "duty_start_hour": "FLOAT",
            "duty_end_hour": "FLOAT",
            "deleted_at": ts,
            "demonstrated_skills": "TEXT",
            "xp": "INTEGER DEFAULT 0",
            "level": "INTEGER DEFAULT 1",
            "joining_date": "DATE",
            "years_experience": "FLOAT DEFAULT 0",
            "pending_skills": "TEXT",
            "manager_id": "INTEGER",
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
        "task_progress": {
            "proof_note": "TEXT",
            "proof_url": "VARCHAR",
        },
        "tenant_settings": {
            "max_teams": "INTEGER DEFAULT 1",
            "subscription_expires_at": ts,
        },
    }


_MAKE_NULLABLE = [
    ("teams", "project_id"),
]


def _drop_not_null_sqlite(connection, table_name: str, column_name: str) -> None:
    result = connection.execute(text(f'PRAGMA table_info("{table_name}")'))
    cols = result.fetchall()
    target = next((c for c in cols if c[1] == column_name), None)
    if target is None or target[3] == 0:
        return
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


def _drop_not_null_pg(connection, table_name: str, column_name: str) -> None:
    result = connection.execute(text(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table_name, "c": column_name})
    row = result.fetchone()
    if row is None or row[0] == "YES":
        return
    connection.execute(text(f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" DROP NOT NULL'))


def ensure_runtime_schema(engine) -> None:
    is_pg = engine.dialect.name == "postgresql"
    additive = _additive_columns(engine)
    allowed_tables = frozenset(additive.keys())
    allowed_columns: frozenset[str] = frozenset(col for cols in additive.values() for col in cols)
    inspector = inspect(engine)

    with engine.begin() as connection:
        for table_name, columns in additive.items():
            assert table_name in allowed_tables
            if table_name not in inspector.get_table_names():
                continue
            existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                assert column_name in allowed_columns
                if column_name in existing_columns:
                    continue
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))

        existing_tables = set(inspector.get_table_names())
        for table_name, column_name in _MAKE_NULLABLE:
            if table_name not in existing_tables:
                continue
            if is_pg:
                _drop_not_null_pg(connection, table_name, column_name)
            else:
                _drop_not_null_sqlite(connection, table_name, column_name)

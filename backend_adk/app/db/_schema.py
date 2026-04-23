from sqlalchemy import inspect, text


ADDITIVE_COLUMNS = {
    "users": {
        "tenant_id": "INTEGER",
        "password_reset_token": "VARCHAR",
        "password_reset_expires": "DATETIME",
    },
    "projects": {
        "tenant_id": "INTEGER",
    },
    "tasks": {
        "tenant_id": "INTEGER",
    },
    "employee_profiles": {
        "tenant_id": "INTEGER",
        "duty_start_hour": "FLOAT",
        "duty_end_hour": "FLOAT",
    },
    "client_profiles": {
        "tenant_id": "INTEGER",
    },
}


def ensure_runtime_schema(engine) -> None:
    inspector = inspect(engine)

    with engine.begin() as connection:
        for table_name, columns in ADDITIVE_COLUMNS.items():
            if table_name not in inspector.get_table_names():
                continue

            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))

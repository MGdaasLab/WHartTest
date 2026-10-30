from django.db import migrations


def fix_last_split_level_column_type(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND column_name = %s
            """,
            ["requirements_requirementdocument", "last_split_level"],
        )
        row = cursor.fetchone()
        if not row:
            return

        data_type = row[0]

        if data_type in {"smallint", "integer", "bigint"}:
            cursor.execute(
                """
                ALTER TABLE requirements_requirementdocument
                ALTER COLUMN last_split_level TYPE varchar(10)
                USING CASE
                    WHEN last_split_level IS NULL THEN 'h2'
                    WHEN last_split_level = 0 THEN 'h2'
                    WHEN last_split_level BETWEEN 1 AND 6 THEN 'h' || last_split_level::text
                    ELSE 'h2'
                END
                """
            )
        elif data_type not in {"character varying", "text"}:
            raise RuntimeError(
                f"Unsupported column type for last_split_level: {data_type}"
            )

        cursor.execute(
            """
            UPDATE requirements_requirementdocument
            SET last_split_level = CASE
                WHEN last_split_level IS NULL OR btrim(last_split_level) = '' THEN 'h2'
                WHEN last_split_level = '0' THEN 'h2'
                WHEN last_split_level ~ '^[1-6]$' THEN 'h' || last_split_level
                WHEN lower(last_split_level) IN ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'auto') THEN lower(last_split_level)
                ELSE 'h2'
            END
            """
        )
        cursor.execute(
            """
            ALTER TABLE requirements_requirementdocument
            ALTER COLUMN last_split_level SET DEFAULT 'h2'
            """
        )
        cursor.execute(
            """
            ALTER TABLE requirements_requirementdocument
            ALTER COLUMN last_split_level SET NOT NULL
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("requirements", "0009_add_last_split_level"),
    ]

    operations = [
        migrations.RunPython(
            fix_last_split_level_column_type, migrations.RunPython.noop
        ),
    ]

"""Application service for database schema and object inspection."""

from collections.abc import Callable
from typing import Any

from postgres_mcp.security.errors import PublicToolError
from postgres_mcp.sql import SafeSqlDriver


class DatabaseInspectionService:
    """Service encapsulating catalog and schema inspection queries."""

    def __init__(self, driver_factory: Callable[..., Any]) -> None:
        self.driver_factory = driver_factory

    async def list_schemas(self, database: str | None = None) -> list[dict[str, Any]]:
        """List all schemas in the database."""
        async with self.driver_factory(database) as sql_driver:
            rows = await sql_driver.execute_query(
                """
                SELECT
                    schema_name,
                    schema_owner,
                    CASE
                        WHEN schema_name LIKE 'pg_%' THEN 'System Schema'
                        WHEN schema_name = 'information_schema' THEN 'System Information Schema'
                        ELSE 'User Schema'
                    END as schema_type
                FROM information_schema.schemata
                ORDER BY schema_type, schema_name
                """
            )
            return [row.cells for row in rows] if rows else []

    async def list_objects(
        self,
        schema_name: str,
        object_type: str = "table",
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """List objects of a given type in a schema."""
        async with self.driver_factory(database) as sql_driver:
            if object_type in ("table", "view"):
                table_type = "BASE TABLE" if object_type == "table" else "VIEW"
                rows = await SafeSqlDriver.execute_param_query(
                    sql_driver,
                    """
                    SELECT table_schema, table_name, table_type
                    FROM information_schema.tables
                    WHERE table_schema = {} AND table_type = {}
                    ORDER BY table_name
                    """,
                    [schema_name, table_type],
                )
                return (
                    [{"schema": row.cells["table_schema"], "name": row.cells["table_name"], "type": row.cells["table_type"]} for row in rows]
                    if rows
                    else []
                )

            if object_type == "sequence":
                rows = await SafeSqlDriver.execute_param_query(
                    sql_driver,
                    """
                    SELECT sequence_schema, sequence_name, data_type
                    FROM information_schema.sequences
                    WHERE sequence_schema = {}
                    ORDER BY sequence_name
                    """,
                    [schema_name],
                )
                return (
                    [
                        {"schema": row.cells["sequence_schema"], "name": row.cells["sequence_name"], "data_type": row.cells["data_type"]}
                        for row in rows
                    ]
                    if rows
                    else []
                )

            if object_type == "extension":
                rows = await sql_driver.execute_query(
                    """
                    SELECT extname, extversion, extrelocatable
                    FROM pg_extension
                    ORDER BY extname
                    """
                )
                return (
                    [{"name": row.cells["extname"], "version": row.cells["extversion"], "relocatable": row.cells["extrelocatable"]} for row in rows]
                    if rows
                    else []
                )

            raise PublicToolError("INVALID_OBJECT_TYPE", f"Unsupported object type: {object_type}")

    async def get_object_details(
        self,
        schema_name: str,
        object_name: str,
        object_type: str = "table",
        database: str | None = None,
    ) -> dict[str, Any]:
        """Get detailed metadata for a database object."""
        async with self.driver_factory(database) as sql_driver:
            if object_type in ("table", "view"):
                col_rows = await SafeSqlDriver.execute_param_query(
                    sql_driver,
                    """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = {} AND table_name = {}
                    ORDER BY ordinal_position
                    """,
                    [schema_name, object_name],
                )
                columns = (
                    [
                        {
                            "column": r.cells["column_name"],
                            "data_type": r.cells["data_type"],
                            "is_nullable": r.cells["is_nullable"],
                            "default": r.cells["column_default"],
                        }
                        for r in col_rows
                    ]
                    if col_rows
                    else []
                )

                con_rows = await SafeSqlDriver.execute_param_query(
                    sql_driver,
                    """
                    SELECT tc.constraint_name, tc.constraint_type, kcu.column_name
                    FROM information_schema.table_constraints AS tc
                    LEFT JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_schema = {} AND tc.table_name = {}
                    """,
                    [schema_name, object_name],
                )

                constraints: dict[str, Any] = {}
                if con_rows:
                    for row in con_rows:
                        cname = row.cells["constraint_name"]
                        ctype = row.cells["constraint_type"]
                        col = row.cells["column_name"]

                        if cname not in constraints:
                            constraints[cname] = {"type": ctype, "columns": []}
                        if col:
                            constraints[cname]["columns"].append(col)

                constraints_list = [{"name": name, **data} for name, data in constraints.items()]

                idx_rows = await SafeSqlDriver.execute_param_query(
                    sql_driver,
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = {} AND tablename = {}
                    """,
                    [schema_name, object_name],
                )

                indexes = [{"name": r.cells["indexname"], "definition": r.cells["indexdef"]} for r in idx_rows] if idx_rows else []

                return {
                    "basic": {"schema": schema_name, "name": object_name, "type": object_type},
                    "columns": columns,
                    "constraints": constraints_list,
                    "indexes": indexes,
                }

            if object_type == "sequence":
                rows = await SafeSqlDriver.execute_param_query(
                    sql_driver,
                    """
                    SELECT sequence_schema, sequence_name, data_type, start_value, increment
                    FROM information_schema.sequences
                    WHERE sequence_schema = {} AND sequence_name = {}
                    """,
                    [schema_name, object_name],
                )
                if rows and rows[0]:
                    row = rows[0]
                    return {
                        "schema": row.cells["sequence_schema"],
                        "name": row.cells["sequence_name"],
                        "data_type": row.cells["data_type"],
                        "start_value": row.cells["start_value"],
                        "increment": row.cells["increment"],
                    }
                return {}

            if object_type == "extension":
                rows = await SafeSqlDriver.execute_param_query(
                    sql_driver,
                    """
                    SELECT extname, extversion, extrelocatable
                    FROM pg_extension
                    WHERE extname = {}
                    """,
                    [object_name],
                )
                if rows and rows[0]:
                    row = rows[0]
                    return {"name": row.cells["extname"], "version": row.cells["extversion"], "relocatable": row.cells["extrelocatable"]}
                return {}

            raise PublicToolError("INVALID_OBJECT_TYPE", f"Unsupported object type: {object_type}")

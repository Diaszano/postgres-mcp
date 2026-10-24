import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from pglast import parse_sql

from postgres_mcp.index.llm_opt import LLMOptimizerTool


@pytest.mark.asyncio
async def test_explain_plan_literals_are_not_logged(caplog):
    sql = "SELECT * FROM accounts WHERE email = 'private@example.com'"
    plan = {"Plan": {"Filter": "email = 'private@example.com'"}}
    explain = MagicMock()
    explain.explain = AsyncMock(return_value=SimpleNamespace(value=plan))
    optimizer = LLMOptimizerTool(MagicMock())
    optimizer._get_table_size = AsyncMock(return_value=100)

    with (
        patch("postgres_mcp.index.llm_opt.ExplainPlanTool", return_value=explain),
        patch.object(optimizer, "_extract_indexes_from_explain_plan_with_columns", AsyncMock(side_effect=RuntimeError("stop"))),
        caplog.at_level(logging.DEBUG, logger="postgres_mcp.index.llm_opt"),
    ):
        with pytest.raises(RuntimeError, match="stop"):
            await optimizer._generate_recommendations([(sql, parse_sql(sql)[0].stmt, 1.0)])

    assert "private@example.com" not in caplog.text

"""Built-in tools for the Store Analytics Agent."""

from .calculator import calculator_tool, calculator_schema
from .query_db import query_db_tool, query_db_schema
from .web_search import web_search_tool, web_search_schema

ALL_TOOLS = [query_db_schema, web_search_schema, calculator_schema]
ALL_TOOL_FUNCTIONS = {
    "query_db": query_db_tool,
    "web_search": web_search_tool,
    "calculator": calculator_tool,
}

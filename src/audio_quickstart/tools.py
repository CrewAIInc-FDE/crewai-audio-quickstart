"""CrewAI tools for the two agents — the same shapes a real field assistant uses.

Patterns mirrored from production engagements (kept generic):

1. Data tools wrap plain, framework-agnostic query functions (testable
   without an LLM), bound to a connection via a factory.
2. Fuzzy asset-name matching resolves whatever the user said to the
   CANONICAL name from the database — the agent is instructed to answer
   with the resolved name, never the user's spelling.
3. "Latest" deliberately skips the in-progress current day
   (ORDER BY date DESC LIMIT 1 OFFSET 1) and falls back to the newest row
   with a caveat note when only one day exists — a small anti-hallucination
   detail that matters in the field.
4. Form tools share one mutable FormSession; caching is disabled on every
   tool (live data must never be served stale; set_field must never be
   deduplicated).
"""

from __future__ import annotations

import difflib
import json
import sqlite3
from typing import Any

from pydantic import BaseModel, Field

from crewai.tools import BaseTool

from audio_quickstart.data import ASSETS, METRIC_COLS, METRIC_LABELS, METRIC_UNITS
from audio_quickstart.forms import FORM_SCHEMAS, FormSession, validate_field


def _never_cache(_args: Any = None, _result: Any = None) -> bool:
    return False


def _as_str(result: Any) -> str:
    return result if isinstance(result, str) else json.dumps(result)


# ---------------------------------------------------------------------------
# Pure query helpers (LLM-free, unit-testable)
# ---------------------------------------------------------------------------

def fuzzy_match_asset(name: str, assets: tuple[str, ...] = ASSETS) -> str | None:
    """Resolve a spoken/typed name to a canonical asset name (or None)."""
    upper = {a.upper(): a for a in assets}
    hits = difflib.get_close_matches(name.upper(), list(upper), n=1, cutoff=0.55)
    return upper[hits[0]] if hits else None


def query_latest(conn: sqlite3.Connection, asset: str, metrics: list[str]) -> dict:
    cols = ", ".join(METRIC_COLS[m] for m in metrics)
    sql = (f"SELECT ASSET_NAME, RECORD_DATE, {cols} FROM DAILY_ASSET_READINGS "
           "WHERE ASSET_NAME = ? ORDER BY RECORD_DATE DESC LIMIT 1 OFFSET 1")
    row = conn.execute(sql, (asset,)).fetchone()
    fallback = False
    if row is None:
        sql = sql.replace(" OFFSET 1", "")
        row = conn.execute(sql, (asset,)).fetchone()
        fallback = True
    if row is None:
        return {"error": f"No data found for asset '{asset}'."}
    result: dict[str, Any] = {
        "asset_name": row[0],
        "record_date": row[1],
        "values": {
            METRIC_LABELS[m]: {"value": row[2 + i], "unit": METRIC_UNITS[m]}
            for i, m in enumerate(metrics)
        },
    }
    if fallback:
        result["note"] = ("Only one day of data available — the value may be "
                          "from an in-progress day and could be incomplete.")
    return result


def query_period(conn: sqlite3.Connection, asset: str, metrics: list[str],
                 aggregation: str) -> dict:
    period, stat = aggregation.split("_", 1)
    days = 7 if period == "weekly" else 30
    fn = {"avg": "AVG", "min": "MIN", "max": "MAX"}[stat]
    cols = ", ".join(f"{fn}({METRIC_COLS[m]})" for m in metrics)
    sql = (f"SELECT ASSET_NAME, {cols} FROM DAILY_ASSET_READINGS "
           "WHERE ASSET_NAME = ? AND RECORD_DATE >= date('now', ?) "
           "GROUP BY ASSET_NAME")
    row = conn.execute(sql, (asset, f"-{days} days")).fetchone()
    if row is None:
        return {"error": f"No data for asset '{asset}' in the {period} window."}
    return {
        "asset_name": row[0],
        "aggregation": aggregation,
        "values": {
            METRIC_LABELS[m]: {"value": round(row[1 + i], 2), "unit": METRIC_UNITS[m]}
            for i, m in enumerate(metrics)
        },
    }


# ---------------------------------------------------------------------------
# Data tools
# ---------------------------------------------------------------------------

_Metric = str  # documented via Field description below; validated in _run

_METRICS_FIELD = Field(description=(
    "One or more of: output_units (questions about output/production), "
    "energy_kwh (energy use), runtime_hours (hours run)."))


class LatestReadingArgs(BaseModel):
    asset_name: str = Field(description="Name of the asset, e.g. 'PUMP A1'.")
    metrics: list[_Metric] = _METRICS_FIELD


class GetLatestReadingTool(BaseTool):
    name: str = "get_latest_reading"
    description: str = ("Latest recorded value(s) for an asset. Use for questions "
                        "like 'what is the current output on pump A1?'")
    args_schema: type[BaseModel] = LatestReadingArgs
    conn: Any = None
    cache_function: Any = _never_cache

    def _run(self, asset_name: str, metrics: list[str]) -> str:
        bad = [m for m in metrics if m not in METRIC_COLS]
        if bad or not metrics:
            return _as_str({"error": f"Unknown metric(s) {bad}. Valid: {list(METRIC_COLS)}"})
        matched = fuzzy_match_asset(asset_name)
        if matched is None:
            return _as_str({"error": f"No asset matching '{asset_name}'. "
                                     "Use list_assets to see what exists."})
        return _as_str(query_latest(self.conn, matched, metrics))


class PeriodStatsArgs(BaseModel):
    asset_name: str = Field(description="Name of the asset, e.g. 'PUMP A1'.")
    metrics: list[_Metric] = _METRICS_FIELD
    aggregation: str = Field(description=(
        "One of: weekly_avg, weekly_min, weekly_max (last 7 days) or "
        "monthly_avg, monthly_min, monthly_max (last 30 days)."))


class GetPeriodStatsTool(BaseTool):
    name: str = "get_period_stats"
    description: str = ("Aggregate statistics over the last week or month for an "
                        "asset. Use for 'average output last week' questions.")
    args_schema: type[BaseModel] = PeriodStatsArgs
    conn: Any = None
    cache_function: Any = _never_cache

    def _run(self, asset_name: str, metrics: list[str], aggregation: str) -> str:
        valid_aggs = {f"{p}_{s}" for p in ("weekly", "monthly") for s in ("avg", "min", "max")}
        if aggregation not in valid_aggs:
            return _as_str({"error": f"Invalid aggregation. Valid: {sorted(valid_aggs)}"})
        bad = [m for m in metrics if m not in METRIC_COLS]
        if bad or not metrics:
            return _as_str({"error": f"Unknown metric(s) {bad}. Valid: {list(METRIC_COLS)}"})
        matched = fuzzy_match_asset(asset_name)
        if matched is None:
            return _as_str({"error": f"No asset matching '{asset_name}'."})
        return _as_str(query_period(self.conn, matched, metrics, aggregation))


class ListAssetsArgs(BaseModel):
    search: str = Field(default="", description="Optional partial name to filter by.")


class ListAssetsTool(BaseTool):
    name: str = "list_assets"
    description: str = ("Asset names matching an optional search term. Use when the "
                        "user asks what assets exist or a name is ambiguous.")
    args_schema: type[BaseModel] = ListAssetsArgs
    cache_function: Any = _never_cache

    def _run(self, search: str = "") -> str:
        if not search:
            return _as_str({"asset_names": list(ASSETS)})
        hits = [a for a in ASSETS if search.upper() in a.upper()]
        if not hits:
            close = difflib.get_close_matches(search.upper(), [a.upper() for a in ASSETS], n=5, cutoff=0.4)
            hits = [a for a in ASSETS if a.upper() in close]
        return _as_str({"asset_names": hits})


def build_data_tools(conn: sqlite3.Connection) -> list[BaseTool]:
    return [
        GetLatestReadingTool(conn=conn),
        GetPeriodStatsTool(conn=conn),
        ListAssetsTool(),
    ]


# ---------------------------------------------------------------------------
# Form tools (share one mutable FormSession)
# ---------------------------------------------------------------------------

class GetFormStateArgs(BaseModel):
    pass


class SetFieldArgs(BaseModel):
    field_name: str = Field(description="Programmatic field name, e.g. 'AssetId'.")
    value: str = Field(description="The value to store.")


class SubmitFormArgs(BaseModel):
    pass


class GetFormStateTool(BaseTool):
    name: str = "get_form_state"
    description: str = "Current form state: which fields are filled / missing."
    args_schema: type[BaseModel] = GetFormStateArgs
    session: Any = None
    cache_function: Any = _never_cache

    def _run(self) -> str:
        return self.session.state_summary()


class SetFieldTool(BaseTool):
    name: str = "set_field"
    description: str = "Set the value of a single form field (validates it)."
    args_schema: type[BaseModel] = SetFieldArgs
    session: Any = None
    cache_function: Any = _never_cache

    def _run(self, field_name: str, value: str) -> str:
        field = next((f for f in self.session.schema.fields if f.name == field_name), None)
        if field is None:
            return f"ERROR: unknown field '{field_name}'. Known: " \
                   f"{[f.name for f in self.session.schema.fields]}"
        normalised, error = validate_field(field, value)
        if error:
            return error
        self.session.data[field_name] = normalised
        return f"OK: {field.label} set to '{normalised}'."


class SubmitFormTool(BaseTool):
    name: str = "submit_form"
    description: str = ("Submit the completed form. Call only after all required "
                        "fields are filled AND the user has confirmed.")
    args_schema: type[BaseModel] = SubmitFormArgs
    session: Any = None
    cache_function: Any = _never_cache

    def _run(self) -> str:
        missing = self.session.missing_required()
        if missing:
            return f"ERROR: cannot submit — missing: {[f.label for f in missing]}"
        self.session.submitted = True
        # Mock submission — a real deployment POSTs to the records system here.
        return ("MOCK SUBMIT OK (no records system connected): "
                + json.dumps(self.session.data))


def build_form_tools(form_type: str) -> tuple[list[BaseTool], FormSession]:
    session = FormSession(FORM_SCHEMAS[form_type])
    return (
        [GetFormStateTool(session=session), SetFieldTool(session=session),
         SubmitFormTool(session=session)],
        session,
    )

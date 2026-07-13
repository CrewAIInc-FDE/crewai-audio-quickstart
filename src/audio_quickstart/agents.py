"""Agent definitions — one per capability, each with its OWN LLM instance.

(Usage counters are scoped to the LLM object; agents sharing one LLM pool
their token numbers. One LLM per agent keeps per-agent accounting honest.)
"""

from __future__ import annotations

from crewai import Agent, LLM

from audio_quickstart.forms import build_form_prompt
from audio_quickstart.tools import build_data_tools, build_form_tools


def _llm() -> LLM:
    return LLM(model="openai/gpt-4o", temperature=0, timeout=60)


def build_data_agent(conn) -> Agent:
    return Agent(
        role="Asset data assistant",
        goal=("Answer questions about asset readings using the available tools. "
              "Be concise. Use the units returned by the tools."),
        backstory=(
            "For the latest value call get_latest_reading. For averages, minimums "
            "or maximums over a period call get_period_stats. If an asset name is "
            "unclear or the user asks what assets exist, call list_assets. "
            "Never invent data — always use a tool. Always refer to assets by the "
            "exact asset_name returned in the tool result, not what the user said. "
            "If the question is not about asset data, say you cannot help with that."
        ),
        llm=_llm(),
        tools=build_data_tools(conn),
        max_iter=10,
        verbose=False,
    )


def build_form_agent(form_type: str):
    tools, session = build_form_tools(form_type)
    agent = Agent(
        role=f"Voice-guided form assistant for the '{session.schema.title}' form",
        goal=("Help the user complete the form: one field at a time, validate each "
              "value with set_field, read the completed form back, submit only on "
              "an explicit 'confirm'."),
        backstory=build_form_prompt(session),
        llm=_llm(),
        tools=tools,
        max_iter=10,
        verbose=False,
    )
    return agent, session

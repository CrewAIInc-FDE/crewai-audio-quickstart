#!/usr/bin/env python
"""Local entry point: `crewai run` (or `uv run run_crew`) executes this."""
import sys

from audio_quickstart.crew import AudioQuickstart


def run():
    """Run the crew locally with a sample (or CLI-provided) question."""
    query = " ".join(sys.argv[1:]) or "What are three interesting facts about the Moon?"
    result = AudioQuickstart().crew().kickoff(inputs={"query": query})
    print(result.raw)


if __name__ == "__main__":
    run()

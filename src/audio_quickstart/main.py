#!/usr/bin/env python
"""Entry points. Local smoke run: two data turns + a form turn, one session."""

import uuid

from audio_quickstart.flow import AssistantFlow


def kickoff() -> None:
    sid = str(uuid.uuid4())
    print(f"--- session {sid} ---")
    for message in (
        "What assets do you have?",
        "What was the latest output on pump A1?",
        "I'd like to file a maintenance report.",
    ):
        print(f"\nYOU: {message}")
        print("ASSISTANT:", AssistantFlow().kickoff(inputs={"id": sid, "message": message}))


def plot() -> None:
    AssistantFlow().plot()


if __name__ == "__main__":
    kickoff()

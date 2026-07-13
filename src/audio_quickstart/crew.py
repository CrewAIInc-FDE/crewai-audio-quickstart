from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task


@CrewBase
class AudioQuickstart():
    """One agent, one task: answer a transcribed question.

    The crew is deliberately tiny — the point of this repo is the wiring
    (audio -> transcription -> kickoff -> answer), not the crew itself.
    Swap this for any crew or flow that takes a text input.
    """

    @agent
    def assistant(self) -> Agent:
        return Agent(
            config=self.agents_config['assistant'],
            verbose=True,
        )

    @task
    def answer_task(self) -> Task:
        return Task(
            config=self.tasks_config['answer_task'],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

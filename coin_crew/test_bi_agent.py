# test_bi_agent.py
from agents import bi_agent
from crewai import Task, Crew, Process

def test_bi_agent_integration():
    task = Task(
        description=(
            "Please query the 'coin_price_change_7d' metric grouped by 'coin_name' "
            "and tell me which coin has the highest 7-day change. "
            "Make an investment recommendation."
        ),
        agent=bi_agent,
        expected_output="A recommendation on which coin to invest in based on metric analysis."
    )

    crew = Crew(
        agents=[bi_agent],
        tasks=[task],
        process=Process.sequential  # Only one agent/task here, but required
    )

    result = crew.kickoff()
    print("BI Agent Output:\n", result)

if __name__ == "__main__":
    test_bi_agent_integration()

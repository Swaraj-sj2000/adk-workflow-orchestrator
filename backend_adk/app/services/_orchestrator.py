# app/services/_orchestrator.py
from sqlalchemy.orm import Session
from typing import List
from app.models._project import Project
from app.services._task_service import create_task, assign_agent
from app.services._agent_service import get_agents
from app.schemas._task import TaskCreate

def generate_tasks(project: Project, db: Session) -> List[int]:
    """
    Mock Orchestrator:
    - Breaks project into mock tasks
    - Assigns available agents evenly
    Returns: list of created task IDs
    """
    # Step 1: Get all agents
    agents = get_agents(db)
    if not agents:
        raise Exception("No agents available to assign tasks")

    # Step 2: Mock task descriptions
    task_descriptions = [
        f"{project.name} - Task {i+1}" for i in range(3)  # 3 tasks per project as mock
    ]

    created_task_ids = []
    for i, desc in enumerate(task_descriptions):
        # Step 3: Assign agent in round-robin
        agent = agents[i % len(agents)]
        task_in = TaskCreate(
            project_id=project.id,
            agent_id=agent.id,
            description=desc,
            status="pending"
        )
        task = create_task(db, task_in)
        created_task_ids.append(task.id)

    return created_task_ids
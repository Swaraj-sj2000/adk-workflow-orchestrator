# app/services/_agent_service.py
from sqlalchemy.orm import Session
from app.models._agent import Agent
from app.schemas._agent import AgentCreate
from typing import List

def create_agent(db: Session, agent_in: AgentCreate) -> Agent:
    agent = Agent(**agent_in.dict())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent

def get_agents(db: Session) -> List[Agent]:
    return db.query(Agent).all()
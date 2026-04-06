# app/api/routes/_agent.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.schemas._agent import AgentCreate, AgentRead
from app.services._agent_service import create_agent, get_agents
from app.core._deps import get_db, get_current_user

router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
    dependencies=[Depends(get_current_user)]
)

@router.post("/", response_model=AgentRead)
def api_create_agent(agent_in: AgentCreate, db: Session = Depends(get_db)):
    return create_agent(db, agent_in)

@router.get("/", response_model=List[AgentRead])
def api_get_agents(db: Session = Depends(get_db)):
    return get_agents(db)
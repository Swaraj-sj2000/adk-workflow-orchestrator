# app/schemas/_agent.py
from pydantic import BaseModel, ConfigDict
from typing import Optional


class AgentCreate(BaseModel):
    name: str
    role: str
    capability: Optional[str] = None


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # ✅ Pydantic v2 (you have pydantic==2.x)

    id: int
    name: str
    role: str
    capability: Optional[str] = None

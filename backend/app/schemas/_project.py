#backend/app/schemas/_project.py

from pydantic import BaseModel

class ProjectCreate(BaseModel):
    name: str
    description: str
    budget: int


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    progress: int
    budget: int
    profit: int

    class Config:
        from_attributes = True
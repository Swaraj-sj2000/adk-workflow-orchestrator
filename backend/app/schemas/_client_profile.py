# app/schemas/_client_profile.py
from pydantic import BaseModel, ConfigDict
from typing import Optional


class ClientProfileCreate(BaseModel):
    user_id: int
    company_name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class ClientProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    company_name: str
    contact_person: Optional[str]
    phone: Optional[str]
    address: Optional[str]

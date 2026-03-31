# backend/app/main.py

from fastapi import FastAPI
from app.db._database import Base, engine
from app.api.routes import _auth
from app.models import _user, _project
from app.api.routes import _auth, _project


Base.metadata.create_all(bind=engine)

app = FastAPI()



app.include_router(_auth.router)
app.include_router(_project.router)

@app.get("/")
def root():
    return {"message": "AI Workflow Orchestrator Running"}
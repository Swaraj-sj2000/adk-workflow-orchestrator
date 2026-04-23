# app/api/routes/_meeting.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core._deps import get_db, get_current_user
from app.models._user import User
from app.models._meeting import Meeting
from app.models._project import Project
from app.schemas._meeting import MeetingCreate, MeetingUpdate, MeetingRead
from typing import List
from datetime import datetime

router = APIRouter(prefix="/meetings", tags=["Meetings"])


@router.post("/", response_model=MeetingRead)
def route_create_meeting(
    meeting: MeetingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a meeting for a project (restricted to caller's tenant)."""
    project = db.query(Project).filter(
        Project.id == meeting.project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Only project admin or system admin can create meetings
    if current_user.role != "admin" and current_user.id != project.admin_id:
        raise HTTPException(status_code=403, detail="Not authorized to create meeting")
    
    new_meeting = Meeting(
        project_id=meeting.project_id,
        created_by=current_user.id,
        title=meeting.title,
        description=meeting.description,
        meeting_type=meeting.meeting_type,
        scheduled_at=meeting.scheduled_at,
        attendees=meeting.attendees or []
    )
    
    db.add(new_meeting)
    db.commit()
    db.refresh(new_meeting)
    
    return new_meeting


@router.get("/project/{project_id}")
def route_get_project_meetings(
    project_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all meetings for a project (restricted to caller's tenant)."""
    # Verify the project belongs to the caller's tenant before returning meetings
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    meetings = db.query(Meeting).filter(
        Meeting.project_id == project_id
    ).order_by(Meeting.created_at.desc()).all()
    return {
        "items": meetings[skip : skip + limit],
        "total": len(meetings),
        "skip": skip,
        "limit": limit,
    }


@router.get("/{meeting_id}", response_model=MeetingRead)
def route_get_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get meeting details (restricted to caller's tenant)."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Verify owning project belongs to caller's tenant
    project = db.query(Project).filter(
        Project.id == meeting.project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")

    return meeting


@router.patch("/{meeting_id}", response_model=MeetingRead)
def route_update_meeting(
    meeting_id: int,
    meeting_update: MeetingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update meeting details (restricted to caller's tenant)."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    project = db.query(Project).filter(
        Project.id == meeting.project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.id != meeting.created_by and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to update meeting")
    
    if meeting_update.title:
        meeting.title = meeting_update.title
    if meeting_update.description:
        meeting.description = meeting_update.description
    if meeting_update.decisions_made:
        meeting.decisions_made = meeting_update.decisions_made
    if meeting_update.status == "completed":
        meeting.completed_at = datetime.utcnow()
    
    db.merge(meeting)
    db.commit()
    db.refresh(meeting)
    
    return meeting


@router.post("/{meeting_id}/decisions", response_model=MeetingRead)
def route_add_meeting_decisions(
    meeting_id: int,
    decisions: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add decisions made in a meeting (restricted to caller's tenant)."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    project = db.query(Project).filter(
        Project.id == meeting.project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.id != meeting.created_by and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to add decisions")
    
    if not meeting.decisions_made:
        meeting.decisions_made = []
    
    for decision in decisions:
        decision["timestamp"] = datetime.utcnow().isoformat()
        meeting.decisions_made.append(decision)
    
    db.merge(meeting)
    db.commit()
    db.refresh(meeting)
    
    return meeting


@router.delete("/{meeting_id}")
def route_delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a meeting (restricted to caller's tenant)."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    project = db.query(Project).filter(
        Project.id == meeting.project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.id != meeting.created_by and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete meeting")
    
    db.delete(meeting)
    db.commit()
    
    return {"success": True, "meeting_id": meeting_id}

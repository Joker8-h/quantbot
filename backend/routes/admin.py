import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import User, Invitation
from auth import get_current_user, require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


class InviteRequest(BaseModel):
    email: str


@router.get("/users")
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.post("/invite")
def invite_user(req: InviteRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    # Check if already a user
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check if already invited
    pending = (
        db.query(Invitation)
        .filter(Invitation.email == req.email, Invitation.used == False)
        .first()
    )
    if pending:
        raise HTTPException(status_code=400, detail="Invitation already sent")

    # Create invitation
    token = str(uuid.uuid4())
    invitation = Invitation(
        email=req.email,
        invited_by=admin.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invitation)
    db.commit()

    return {
        "message": f"Invitation sent to {req.email}",
        "invitation_url": f"/register?token={token}",
        "token": token,
    }


@router.get("/invitations")
def list_invitations(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    invitations = (
        db.query(Invitation)
        .order_by(Invitation.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": inv.id,
            "email": inv.email,
            "used": inv.used,
            "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        }
        for inv in invitations
    ]


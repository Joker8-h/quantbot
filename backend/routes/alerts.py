from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import User, AlertConfig, UserContact
from auth import get_current_user
from services.telegram import send_telegram
from services.whatsapp import send_whatsapp, get_whatsapp_status

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertToggleRequest(BaseModel):
    alert_type: str
    channel: str
    is_active: bool


class ContactUpdateRequest(BaseModel):
    phone: str = None
    telegram_chat_id: str = None


@router.get("/")
def get_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alerts = db.query(AlertConfig).filter(AlertConfig.user_id == user.id).all()
    contact = db.query(UserContact).filter(UserContact.user_id == user.id).first()

    alert_types = ["trade_closed", "daily_profit", "weekly_report", "system_pause", "large_loss", "system_error"]
    channels = ["whatsapp", "telegram"]

    result = {}
    for at in alert_types:
        result[at] = {}
        for ch in channels:
            found = next((a for a in alerts if a.alert_type == at and a.channel == ch), None)
            result[at][ch] = found.is_active if found else (at in ["trade_closed", "daily_profit", "system_pause"])

    return {
        "alerts": result,
        "contact": {
            "phone": contact.phone if contact else None,
            "telegram_chat_id": contact.telegram_chat_id if contact else None,
        },
    }


@router.put("/toggle")
def toggle_alert(req: AlertToggleRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = (
        db.query(AlertConfig)
        .filter(
            AlertConfig.user_id == user.id,
            AlertConfig.alert_type == req.alert_type,
            AlertConfig.channel == req.channel,
        )
        .first()
    )

    if existing:
        existing.is_active = req.is_active
    else:
        alert = AlertConfig(
            user_id=user.id,
            alert_type=req.alert_type,
            channel=req.channel,
            is_active=req.is_active,
        )
        db.add(alert)

    db.commit()
    return {"message": f"Alert {req.alert_type} on {req.channel} set to {req.is_active}"}


@router.put("/contact")
def update_contact(req: ContactUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contact = db.query(UserContact).filter(UserContact.user_id == user.id).first()

    if not contact:
        contact = UserContact(user_id=user.id)
        db.add(contact)

    if req.phone is not None:
        contact.phone = req.phone
    if req.telegram_chat_id is not None:
        contact.telegram_chat_id = req.telegram_chat_id

    db.commit()
    return {"message": "Contact updated"}


@router.post("/test-telegram")
async def test_telegram(user: User = Depends(get_current_user)):
    success = await send_telegram(
        "🤖 <b>QuantBot</b>\nConexión exitosa! Las alertas llegarán a este chat.",
    )
    if success:
        return {"message": "Telegram test message sent"}
    raise HTTPException(status_code=500, detail="Failed to send Telegram message")


@router.post("/test-whatsapp")
async def test_whatsapp(user: User = Depends(get_current_user)):
    contact = None
    db = next(get_db())
    try:
        contact = db.query(UserContact).filter(UserContact.user_id == user.id).first()
    finally:
        db.close()

    phone = contact.phone if contact and contact.phone else None
    success = await send_whatsapp(
        "🤖 *QuantBot*\nConexión exitosa! Las alertas llegarán por WhatsApp.",
        phone=phone,
    )
    if success:
        return {"message": "WhatsApp test message sent"}
    raise HTTPException(status_code=500, detail="Failed to send WhatsApp message")


@router.get("/whatsapp-status")
async def whatsapp_status(user: User = Depends(get_current_user)):
    return await get_whatsapp_status()

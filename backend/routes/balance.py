from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User, Trade, BalanceSnapshot, SystemStatus
from auth import get_current_user

router = APIRouter(prefix="/api", tags=["balance"])


@router.get("/balance")
def get_balance(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Get latest balance snapshot
    snapshot = (
        db.query(BalanceSnapshot)
        .filter(BalanceSnapshot.user_id == user.id)
        .order_by(BalanceSnapshot.timestamp.desc())
        .first()
    )

    # Get today's PnL
    from datetime import datetime, timezone, timedelta
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_trades = (
        db.query(Trade)
        .filter(Trade.user_id == user.id, Trade.exit_time >= today_start, Trade.status == "closed")
        .all()
    )
    today_pnl = sum(t.pnl_usd or 0 for t in today_trades)

    # Get this week's PnL
    week_start = today_start - timedelta(days=today_start.weekday())
    week_trades = (
        db.query(Trade)
        .filter(Trade.user_id == user.id, Trade.exit_time >= week_start, Trade.status == "closed")
        .all()
    )
    week_pnl = sum(t.pnl_usd or 0 for t in week_trades)

    # Get this month's PnL
    month_start = today_start.replace(day=1)
    month_trades = (
        db.query(Trade)
        .filter(Trade.user_id == user.id, Trade.exit_time >= month_start, Trade.status == "closed")
        .all()
    )
    month_pnl = sum(t.pnl_usd or 0 for t in month_trades)

    # Get total PnL
    all_trades = (
        db.query(Trade)
        .filter(Trade.user_id == user.id, Trade.status == "closed")
        .all()
    )
    total_pnl = sum(t.pnl_usd or 0 for t in all_trades)

    # Currency conversion
    from config import config
    rate = config.USD_TO_COP_RATE
    currency = user.currency_preference

    def convert(usd):
        return round(usd * rate, 2) if currency == "COP" else round(usd, 2)

    symbol = "COP" if currency == "COP" else "USD"

    return {
        "total_balance": convert(snapshot.total_balance_usd if snapshot else 100.0),
        "available": convert(snapshot.available_usd if snapshot else 100.0),
        "unrealized_pnl": convert(snapshot.unrealized_pnl_usd if snapshot else 0.0),
        "today_pnl": convert(today_pnl),
        "week_pnl": convert(week_pnl),
        "month_pnl": convert(month_pnl),
        "total_pnl": convert(total_pnl),
        "currency": currency,
        "symbol": symbol,
        "usd_to_cop_rate": rate,
    }


@router.get("/stats")
def get_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import datetime, timezone, timedelta

    all_trades = (
        db.query(Trade)
        .filter(Trade.user_id == user.id, Trade.status == "closed")
        .all()
    )

    total_trades = len(all_trades)
    winning = sum(1 for t in all_trades if (t.pnl_usd or 0) > 0)
    losing = sum(1 for t in all_trades if (t.pnl_usd or 0) <= 0)
    win_rate = (winning / total_trades * 100) if total_trades > 0 else 0

    gross_profit = sum(t.pnl_usd for t in all_trades if (t.pnl_usd or 0) > 0)
    gross_loss = abs(sum(t.pnl_usd for t in all_trades if (t.pnl_usd or 0) <= 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    return {
        "total_trades": total_trades,
        "winning_trades": winning,
        "losing_trades": losing,
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
    }


@router.get("/trades")
def get_trades(limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trades = (
        db.query(Trade)
        .filter(Trade.user_id == user.id)
        .order_by(Trade.entry_time.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "pnl": t.pnl,
            "pnl_usd": t.pnl_usd,
            "fee": t.fee,
            "entry_time": t.entry_time.isoformat() if t.entry_time else None,
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            "exit_reason": t.exit_reason,
            "status": t.status,
        }
        for t in trades
    ]


@router.get("/system/status")
def get_system_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    status_obj = db.query(SystemStatus).filter(SystemStatus.user_id == user.id).first()

    if not status_obj:
        return {
            "is_running": False,
            "last_trade_time": None,
            "last_signal": None,
            "total_pnl_usd": 0.0,
            "today_pnl_usd": 0.0,
        }

    return {
        "is_running": status_obj.is_running,
        "last_trade_time": status_obj.last_trade_time.isoformat() if status_obj.last_trade_time else None,
        "last_signal": status_obj.last_signal,
        "total_pnl_usd": status_obj.total_pnl_usd,
        "today_pnl_usd": status_obj.today_pnl_usd,
    }


@router.post("/system/pause")
def pause_system(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    status_obj = db.query(SystemStatus).filter(SystemStatus.user_id == user.id).first()
    if status_obj:
        status_obj.is_running = False
        db.commit()
    return {"message": "System paused", "is_running": False}


@router.post("/system/resume")
def resume_system(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    status_obj = db.query(SystemStatus).filter(SystemStatus.user_id == user.id).first()
    if status_obj:
        status_obj.is_running = True
        db.commit()
    return {"message": "System resumed", "is_running": True}


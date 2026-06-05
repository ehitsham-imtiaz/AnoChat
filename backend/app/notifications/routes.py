from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.service import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Notification, User, WebPushSubscription
from app.notifications.service import get_or_create_preferences
from app.schemas import (
    NotificationOut,
    NotificationPreferenceOut,
    NotificationPreferenceUpdate,
    PushConfigOut,
    PushSubscriptionIn,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
settings = get_settings()


@router.get("", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .order_by(Notification.created_at.desc())
        .limit(25)
        .all()
    )


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .update({"is_read": True}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True}


@router.get("/push-config", response_model=PushConfigOut)
def push_config():
    enabled = bool(settings.vapid_public_key and settings.vapid_private_key)
    return PushConfigOut(enabled=enabled, public_key=settings.vapid_public_key or None)


@router.get("/preferences", response_model=NotificationPreferenceOut)
def get_preferences(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    preferences = get_or_create_preferences(db, current_user.id)
    db.commit()
    db.refresh(preferences)
    return preferences


@router.put("/preferences", response_model=NotificationPreferenceOut)
def update_preferences(
    payload: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    preferences = get_or_create_preferences(db, current_user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(preferences, key, value)
    db.commit()
    db.refresh(preferences)
    return preferences


@router.post("/subscriptions")
def save_subscription(
    payload: PushSubscriptionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = db.query(WebPushSubscription).filter(WebPushSubscription.endpoint == payload.endpoint).first()
    if not subscription:
        subscription = WebPushSubscription(user_id=current_user.id, endpoint=payload.endpoint)
        db.add(subscription)
    subscription.user_id = current_user.id
    subscription.p256dh = payload.keys.p256dh
    subscription.auth = payload.keys.auth
    subscription.active = True
    db.commit()
    return {"ok": True}


@router.delete("/subscriptions")
def delete_subscription(
    payload: PushSubscriptionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = (
        db.query(WebPushSubscription)
        .filter(WebPushSubscription.user_id == current_user.id, WebPushSubscription.endpoint == payload.endpoint)
        .first()
    )
    if subscription:
        subscription.active = False
        db.commit()
    return {"ok": True}

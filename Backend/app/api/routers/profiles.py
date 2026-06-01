from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import success_response
from app.services.profile_service import list_avatar_profiles, list_voice_profiles

router = APIRouter()


@router.get("/voice-profiles")
def voices(db: Session = Depends(get_db)) -> dict:
    return success_response(list_voice_profiles(db))


@router.get("/avatar-profiles")
def avatars(db: Session = Depends(get_db)) -> dict:
    return success_response(list_avatar_profiles(db))

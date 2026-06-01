from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AvatarProfileModel, VoiceProfileModel
from app.services.serializers import avatar_profile_to_dict, voice_profile_to_dict


def list_voice_profiles(db: Session) -> list[dict]:
    return [voice_profile_to_dict(item) for item in db.scalars(select(VoiceProfileModel)).all()]


def list_avatar_profiles(db: Session) -> list[dict]:
    return [avatar_profile_to_dict(item) for item in db.scalars(select(AvatarProfileModel)).all()]

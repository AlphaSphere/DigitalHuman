from fastapi import APIRouter

from app.core.exceptions import success_response
from app.services.music_service import list_music_tracks

router = APIRouter()


@router.get("/music-tracks")
def music_tracks() -> dict:
    return success_response(list_music_tracks())

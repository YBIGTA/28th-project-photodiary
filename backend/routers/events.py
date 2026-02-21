from fastapi import APIRouter, Depends

from db.schema import get_connection
from db.crud import get_last_event
from backend.dependencies import get_current_user_id

router = APIRouter()


@router.get("/last")
def get_last_event_endpoint(user_id: int = Depends(get_current_user_id)):
    conn = get_connection()
    try:
        event = get_last_event(conn, user_id)
        return event
    finally:
        conn.close()

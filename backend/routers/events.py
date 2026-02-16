from fastapi import APIRouter
from db.schema import get_connection
from db.crud import get_last_event, list_unclustered_photos

router = APIRouter()

USER_ID = 1

@router.get("/last")
def get_last_event_endpoint():
    conn = get_connection()
    try:
        event = get_last_event(conn, USER_ID)
        return event
    finally:
        conn.close()

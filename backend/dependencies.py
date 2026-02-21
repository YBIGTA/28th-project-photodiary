"""공통 의존성 — JWT 토큰에서 user_id 추출."""

from fastapi import Header, HTTPException

from backend.services.auth import decode_access_token


def get_current_user_id(authorization: str = Header(default=None)) -> int:
    """Authorization 헤더에서 Bearer 토큰을 파싱하여 user_id를 반환한다.

    Parameters
    ----------
    authorization : str
        "Bearer <token>" 형식의 Authorization 헤더.

    Returns
    -------
    int
        현재 인증된 사용자 ID.

    Raises
    ------
    HTTPException
        토큰이 없거나 유효하지 않을 때 401.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="유효하지 않은 인증 형식입니다.")

    token = authorization[7:]  # "Bearer " 이후
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="토큰이 만료되었거나 유효하지 않습니다.")

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

    return user_id

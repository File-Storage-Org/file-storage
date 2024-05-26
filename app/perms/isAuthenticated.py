import jwt
from fastapi import status, HTTPException, Request

from app.config import JWT_SECRET_KEY, ALGORITHM


async def is_authenticated(request: Request):
    try:
        token = request.headers.get("Authorization").split("Bearer ")[1]
        if token:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
            is_auth: bool = payload.get("isAuth")
            if not is_auth:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

            return payload.get("user_id", None)

    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

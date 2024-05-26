import jwt

from fastapi import Request, HTTPException, status
from datetime import datetime
from .config import (
    JWT_SECRET_KEY,
    ALGORITHM,
)


async def is_token_expired(request: Request):
    token = request.headers.get("Authorization").split("Bearer ")[1]
    # Here's options verify_exp parameter
    # It is False because jwt decode func is checking exp by itself
    # As we need to check token exp by ourselves, then it must equal False
    payload = jwt.decode(
        token, JWT_SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False}
    )
    exp = payload.get("exp")
    if exp:
        now = datetime.utcnow()
        expiration_datetime = datetime.utcfromtimestamp(exp)
        if now > expiration_datetime:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been expired",
            )
    else:
        # If 'exp' claim is not present, consider token as expired
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been expired",
        )

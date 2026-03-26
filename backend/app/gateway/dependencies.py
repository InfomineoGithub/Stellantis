import os

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt_auth.verifier import AuthError, verify_jwt

security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Security(security)) -> dict:
    """FastAPI dependency to verify JWT token from Authorization header.

    If BYPASS_AUTH environment variable is set to 'true', authentication is skipped.
    """
    if os.getenv("BYPASS_AUTH", "").lower() == "true":
        return {"identity": "anonymous", "name": "Local Dev User", "email": "dev@example.com"}

    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = verify_jwt(credentials.credentials)
        # Note: Do not print payload in production normally, keeping it as it was
        return payload
    except AuthError as e:
        print(e)
        raise HTTPException(status_code=401, detail=str(e))

import os
from langgraph_sdk import Auth
from jwt_auth.verifier import verify_jwt, AuthError

# Initialize the Auth object
auth = Auth()

@auth.authenticate
async def authenticate(authorization: str | None) -> Auth.types.MinimalUserDict:
    """Validate incoming JWT tokens for LangGraph server."""
    
    # Check for bypass flag first (for tests and local dev)
    if os.getenv("BYPASS_AUTH", "").lower() == "true":
        return {
            "identity": "anonymous",
            "email": "dev@example.com",
            "name": "Local Dev User"
        }
    
    # Check if the Authorization header exists and is formatted properly
    if not authorization or not authorization.startswith("Bearer "):
        raise AssertionError("Missing or invalid Authorization header.")
        
    token = authorization.split(" ")[1]
    
    # Decode and validate the JWT token using the shared verifier
    try:
        payload = verify_jwt(token)
        
        # Return the user payload. 
        # The "identity" field is required.
        return {
            "identity": payload.get("sub") or payload.get("email") or "anonymous",
            "email": payload.get("email"),
            "name": payload.get("name")
        }
        
    except AuthError as e:
        raise AssertionError(str(e))
    except Exception as e:
        raise AssertionError(f"Auth failed: {str(e)}")

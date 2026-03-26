import json
import logging
from jwt_auth.verifier import verify_jwt, _try_jwks, _jwks_url

def main():
    import httpx
    # Login as the user we created
    auth_url = "http://localhost:2026/api/auth/sign-in/email"
    res = httpx.post(auth_url, json={"email": "admin@stellantis.local", "password": "Stellantis2024!"})
    res.raise_for_status()
    # Now get the token using the session cookie
    cookies = res.cookies
    token_url = "http://localhost:2026/api/auth/token"
    res2 = httpx.get(token_url, cookies=cookies)
    res2.raise_for_status()
    token = res2.json()["token"]
    
    print("Token fetched. Length:", len(token))
    try:
        payload = verify_jwt(token)
        print("verify_jwt succeeded!", payload)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

import hashlib
import uuid
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException

class Authenticator:
    def __init__(self, issuer, audience, jwks_url):
        if not issuer.startswith("https://") or not jwks_url.startswith("https://"):
            raise ValueError("HTTPS issuer and JWKS required")
        self.issuer, self.audience = issuer, audience
        self.jwks = PyJWKClient(jwks_url, cache_keys=True, lifespan=300)

    def verify(self, token):
        try:
            header=jwt.get_unverified_header(token)
            if header.get("alg") not in {"RS256","ES256"}: raise ValueError("algorithm")
            key=self.jwks.get_signing_key_from_jwt(token).key
            claims=jwt.decode(token,key,algorithms=["RS256","ES256"],issuer=self.issuer,audience=self.audience,options={"require":["sub","exp","iat","iss","aud"]})
            claims["sub"]=str(uuid.UUID(claims["sub"]))
            return claims
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise HTTPException(401,"Invalid or expired access token") from None

def digest(token): return hashlib.sha256(token.encode()).hexdigest()

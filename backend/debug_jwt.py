import jwt

print(jwt.__version__)

try:
    jwt.decode("eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.e30.signature", "key", algorithms=["EdDSA"])
except Exception as e:
    print(repr(e))

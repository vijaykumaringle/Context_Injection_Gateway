import os
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "yoursecretkey_for_testing")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

def create_token(user_id: str, role: str):
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode = {"sub": user_id, "role": role, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

if __name__ == "__main__":
    print("--- Test JWTs ---")
    print(f"User (HR): {create_token('user_123', 'user')}")
    print(f"Admin (Ops): {create_token('admin_999', 'admin')}")
    print(f"Healthcare Provider: {create_token('doctor_007', 'healthcare_provider')}")
    print(f"Developer (Sec): {create_token('dev_555', 'developer')}")

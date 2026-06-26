import hashlib
from database import SessionLocal
from models import APIUser

def find_user_by_pseudo_id(pseudo_id: str):
    print(f"Searching for identity behind pseudo_id '{pseudo_id}'...")
    
    db = SessionLocal()
    user = db.query(APIUser).filter(APIUser.user_pseudo_id == pseudo_id).first()
    
    if user:
        print(f"🚨 MATCH FOUND! 🚨")
        print(f"The identity belongs to: {user.user_id}")
        print(f"Registered Role: {user.role}")
    else:
        print("No matching user found in the database. The user might have been deleted, or the hash is invalid.")
        
    db.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python resolve_audit_user.py <user_pseudo_id>")
    else:
        target_id = sys.argv[1]
        find_user_by_pseudo_id(target_id)

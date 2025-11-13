from fastapi import Depends, HTTPException
from firebase_admin import firestore
from app.core.firebase_service import FirebaseService

firebase_service = FirebaseService()


def get_firestore():
    return firebase_service.get_firestore()


def verify_token(uid: str = Depends(firebase_service.verify_token)):
    return uid


def get_current_user_profile(
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
):
    profile_ref = db.collection("profiles").document(uid).get()
    if not profile_ref.exists:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile_ref.to_dict()


def require_bus_attendant(
    profile: dict = Depends(get_current_user_profile),
):
    if profile.get("user_type") != "bus_attendant":
        raise HTTPException(status_code=403, detail="Bus attendant access required")
    return profile


# not sure yet if needed
def require_normal_user(
    profile: dict = Depends(get_current_user_profile),
):
    if profile.get("user_type") != "normal_user":
        raise HTTPException(status_code=403, detail="Normal user access required")
    return profile

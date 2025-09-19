from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import firestore

# from app.core.firebase_service import get_firestore, verify_token
from app.profiles.schema import UserProfile, UserProfileResponse, UserProfileUpdate
from app.core.dependencies import get_firestore, verify_token

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("/", response_model=UserProfileResponse)
def create_profile(
    profile: UserProfile,
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
):
    profile_ref = db.collection("profiles").document(uid)
    if profile_ref.get().exists:
        raise HTTPException(status_code=400, detail="Profile already exists")

    profile_ref.set(profile.dict())
    return {"id": uid, "message": "Profile created successfully"}


@router.get("/me", response_model=UserProfile)
def get_my_profile(
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
):
    profile_ref = db.collection("profiles").document(uid).get()
    if not profile_ref.exists:
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile_ref.to_dict()


@router.put("/", response_model=UserProfileResponse)
def update_profile(
    profile: UserProfileUpdate,
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
):
    profile_ref = db.collection("profiles").document(uid)
    if not profile_ref.get().exists:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile_ref.update(profile.to_update_dict())
    return {"id": uid, "message": "Profile updated successfully"}

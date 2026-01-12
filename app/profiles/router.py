from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import firestore, auth
import requests, os

from app.profiles.schema import (
    UserProfile,
    UserProfileResponse,
    UserProfileUpdate,
    UsernameLoginRequest,
    FCMToken,
)
from app.core.dependencies import get_firestore, verify_token

from app.core.notification_service import NotificationService

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

    username_lower = profile.username.lower()

    existing = (
        db.collection("profiles")
        .where("username_lower", "==", username_lower)
        .limit(1)
        .get()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    profile_ref.set(
        {
            **profile.dict(exclude={"username"}),
            "username": profile.username,
            "username_lower": username_lower,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
    )

    return {"id": uid, "message": "Profile created successfully"}


@router.post("/login")
def login_with_username(
    payload: UsernameLoginRequest,
    db: firestore.Client = Depends(get_firestore),
):
    username_lower = payload.username.lower()

    profiles = (
        db.collection("profiles")
        .where("username_lower", "==", username_lower)
        .limit(1)
        .get()
    )

    if not profiles:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    uid = profiles[0].id

    try:
        user = auth.get_user(uid)
        email = user.email
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    response = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={os.getenv('FIREBASE_API_KEY')}",
        json={
            "email": email,
            "password": payload.password,
            "returnSecureToken": True,
        },
        timeout=10,
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    return response.json()


@router.get("/me", response_model=UserProfile)
def get_my_profile(
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
):
    snapshot = db.collection("profiles").document(uid).get()
    if not snapshot.exists:
        raise HTTPException(status_code=404, detail="Profile not found")

    data = snapshot.to_dict()
    data.pop("username_lower", None)
    return data


@router.put("/", response_model=UserProfileResponse)
def update_profile(
    profile: UserProfileUpdate,
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
):
    profile_ref = db.collection("profiles").document(uid)
    if not profile_ref.get().exists:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = profile.to_update_dict()
    update_data["updated_at"] = firestore.SERVER_TIMESTAMP

    profile_ref.update(update_data)
    return {"id": uid, "message": "Profile updated successfully"}


@router.post("/register-fcm")
def register_fcm_token(
    token: FCMToken,
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
):
    fcm_token_value = token.fcm_token

    profile_ref = db.collection("profiles").document(uid)
    if not profile_ref.get().exists:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile_ref.update({"fcm_token": fcm_token_value})

    return {"message": "FCM token registered successfully"}

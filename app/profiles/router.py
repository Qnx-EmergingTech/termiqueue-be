from fastapi import APIRouter, Depends, HTTPException, Query
from firebase_admin import firestore, auth
from datetime import datetime
import requests, os

from app.profiles.schema import (
    UserProfile,
    UserProfileResponse,
    UserProfileUpdate,
    SignupRequest,
    UsernameLoginRequest,
    FCMToken,
    TripHistoryResponse,
    TripSummary,
)

from app.profiles.service import ProfileService
from app.core.dependencies import get_firestore, verify_token

from app.core.notification_service import NotificationService

router = APIRouter(prefix="/profiles", tags=["profiles"])


def get_profile_service(
    db: firestore.Client = Depends(get_firestore),
) -> ProfileService:
    return ProfileService(db)


@router.post("/", response_model=UserProfileResponse)
def create_profile(
    profile: UserProfile,
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
):
    profile_ref = db.collection("profiles").document(uid)
    snapshot = profile_ref.get()

    if not snapshot.exists:
        raise HTTPException(status_code=404, detail="Account not found")

    data = snapshot.to_dict()
    if "first_name" in data:
        raise HTTPException(status_code=400, detail="Profile already completed")

    profile_ref.update(
        {
            **profile.dict(),
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
    )

    return {"id": uid, "message": "Profile created successfully"}


@router.post("/signup")
def signup(
    payload: SignupRequest,
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
):
    username_lower = payload.username.lower()

    existing = (
        db.collection("profiles")
        .where("username_lower", "==", username_lower)
        .limit(1)
        .get()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    db.collection("profiles").document(uid).set(
        {
            "username": payload.username,
            "username_lower": username_lower,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
    )

    return {"message": "Signup completed"}


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


@router.get("/me/trips/all", response_model=TripHistoryResponse)
def get_all_my_trips(
    uid: str = Depends(verify_token),
    profile_service: ProfileService = Depends(get_profile_service),
):
    return profile_service.get_trip_history(user_id=uid)


@router.get("/me/trips/{trip_id}", response_model=TripSummary)
def get_my_trip_detail(
    trip_id: str,
    uid: str = Depends(verify_token),
    profile_service: ProfileService = Depends(get_profile_service),
):
    return profile_service.get_trip_by_id(
        user_id=uid,
        trip_id=trip_id,
    )

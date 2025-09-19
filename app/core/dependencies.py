from fastapi import Depends
from app.core.firebase_service import FirebaseService

firebase_service = FirebaseService()


def get_firestore():
    return firebase_service.get_firestore()


def verify_token(uid: str = Depends(firebase_service.verify_token)):
    return uid

import firebase_admin
from firebase_admin import credentials, firestore, auth, messaging
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

security = HTTPBearer()


class FirebaseService:
    def __init__(self):
        self.cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.cred_path)
            firebase_admin.initialize_app(cred)

    def get_firestore(self):
        return firestore.client()

    def verify_token(
        self, credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
        id_token = credentials.credentials
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token["uid"]
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    # FCM firebase service
    def send_fcm(self, title: str, body: str, token: str):
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=token,
        )
        response = messaging.send(message)
        return response

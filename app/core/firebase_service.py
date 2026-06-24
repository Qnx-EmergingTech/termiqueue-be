import firebase_admin
from firebase_admin import credentials, firestore, auth, messaging
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger
import os

security = HTTPBearer()


class FirebaseService:
    def __init__(self):
        self.cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.cred_path)
            firebase_admin.initialize_app(cred)
            logger.info(f"Firebase initialized — credentials={self.cred_path}")
        else:
            logger.info("Firebase already initialized — skipping")

    def get_firestore(self):
        return firestore.client()

    def verify_token(
        self, credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
        id_token = credentials.credentials
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token["uid"]
        except Exception as e:
            logger.warning(f"Token verification failed — {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    # FCM firebase service
    def send_fcm(self, title: str, body: str, token: str):
        try:
            response = messaging.send(
                messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    token=token,
                )
            )
            logger.info(f"FCM sent — title='{title}' token={token[:20]}...")
            return response
        except Exception as e:
            logger.error(
                f"FCM send failed — title='{title}' token={token[:20]}... error={str(e)}"
            )
            raise

from firebase_admin import messaging
from loguru import logger


class NotificationService:
    def send_to_token(self, token: str, title: str, body: str, data: dict = None):
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=data,
                token=token,
            )
            response = messaging.send(message)
            logger.info(
                f"FCM notification sent — title='{title}' token={token[:20]}..."
            )
            return response
        except Exception as e:
            logger.error(
                f"FCM notification failed — title='{title}' token={token[:20]}... error={str(e)}"
            )
            return None

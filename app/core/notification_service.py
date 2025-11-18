from firebase_admin import messaging


class NotificationService:
    def send_to_token(self, token: str, title: str, body: str):
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body), token=token
        )
        return messaging.send(message)

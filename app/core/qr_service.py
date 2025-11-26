import base64
import io
import json
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

import qrcode
from cryptography.fernet import Fernet, InvalidToken

load_dotenv()

QR_SECRET_KEY = os.getenv("QR_SECRET_KEY", None)


class QRService:
    def __init__(self, key: str | None = None):
        key_to_use = key or QR_SECRET_KEY
        if not key_to_use:
            raise RuntimeError("QR secret key not found")
        if isinstance(key_to_use, str):
            key_bytes = key_to_use.encode()
        else:
            key_bytes = key_to_use
        self.fernet = Fernet(key_bytes)

    def _serialize_and_encrypt(self, payload: dict) -> bytes:
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        token = self.fernet.encrypt(raw)
        return token

    def _decrypt_and_deserialize(self, token: bytes) -> dict:
        raw = self.fernet.decrypt(token)
        return json.loads(raw.decode("utf-8"))

    def generate_qr_base64(self, payload: dict, image_size: int = 350) -> str:
        payload = dict(payload)
        if "issued_at" not in payload:
            payload["issued_at"] = datetime.now(timezone.utc).isoformat()

        enc = self._serialize_and_encrypt(payload)

        token_str = enc.decode("utf-8")

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_Q,
            box_size=10,
            border=4,
        )

        wrapper = {"v": 1, "t": token_str}
        qr.add_data(json.dumps(wrapper, separators=(",", ":")))
        qr.make(fit=True)
        img = qr.make_image()

        img = img.resize((image_size, image_size))

        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        return b64

    def decrypt_token_wrapper(self, wrapper_json: str) -> dict:
        wrapper = json.loads(wrapper_json)
        token_str = wrapper.get("t")
        if not token_str:
            raise ValueError("Invalid QR wrapper: missing token")
        try:
            return self._decrypt_and_deserialize(token_str.encode("utf-8"))
        except InvalidToken as e:
            raise InvalidToken from e

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from firebase_admin import firestore, auth
from app.core.geolocation_service import GeolocationService
from app.core.dependencies import get_firestore, verify_token
from app.queues.service import QueueService
from app.queues.schema import CreateQueueInfo, GeofenceCheck, QueueInfoResponse
from app.core.qr_service import QRService
from datetime import datetime, timezone
from app.core.ws_manager import ws_manager

router = APIRouter(prefix="/queues", tags=["queues"])


def get_queue_service(db: firestore.Client = Depends(get_firestore)) -> QueueService:
    return QueueService(db)


@router.get("/", response_model=list[QueueInfoResponse])
def get_queues(queue_service: QueueService = Depends(get_queue_service)):
    queues = queue_service.get_queues()
    return queues


@router.post("/")
def create_terminal_queue(
    queue_info: CreateQueueInfo,
    queue_service: QueueService = Depends(get_queue_service),
):
    queue_id = queue_service.create_terminal_queue(
        queue_info.destination, queue_info.priority_seat
    )
    return {"message": "Terminal Queue created successfully.", "queue_id": queue_id}


@router.post("/check-geofence")
def check_geofence(
    loc: GeofenceCheck,
    db: firestore.Client = Depends(get_firestore),
):
    geolocation_service = GeolocationService(db)
    if geolocation_service.is_within_geofence(loc.lat, loc.lon):
        return {"can_join": True, "message": "User is within the geofence."}
    else:
        return {"can_join": False, "message": "User is outside the geofence."}


@router.post("/{queue_id}/join")
async def join_queue(
    queue_id: str,
    queue_service: QueueService = Depends(get_queue_service),
    uid: str = Depends(verify_token),
):
    result = await queue_service.join_queue(uid, queue_id)
    return result


@router.post("/{queue_id}/leave")
async def leave_queue(
    queue_id: str,
    queue_service: QueueService = Depends(get_queue_service),
    uid: str = Depends(verify_token),
):
    return await queue_service.leave_queue(uid, queue_id)


@router.get("/{queue_id}/me/status")
def get_queue_status(
    queue_id: str,
    queue_service: QueueService = Depends(get_queue_service),
    uid: str = Depends(verify_token),
):
    data = queue_service.get_queue_status(uid, queue_id)
    return data


@router.get("/{queue_id}/my-qr-code")
def get_my_qr_code(
    queue_id: str,
    queue_service: QueueService = Depends(get_queue_service),
    uid: str = Depends(verify_token),
):
    passenger = queue_service.get_passenger(uid, queue_id)
    full_name = passenger.get("full_name")
    ticket_number = passenger.get("ticket_number")
    if ticket_number is None:
        raise HTTPException(
            status_code=500, detail="Passenger record missing ticket_number"
        )

    issued_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "user_id": uid,
        "queue_id": queue_id,
        "full_name": full_name,
        "ticket_number": ticket_number,
        "issued_at": issued_at,
    }

    qr_service = QRService()
    qr_b64 = qr_service.generate_qr_base64(payload)

    return {"qr_base64": qr_b64, "message": "QR code generated successfully."}


@router.websocket("/ws/queues/{queue_id}")
async def queue_ws(websocket: WebSocket, queue_id: str):
    await ws_manager.connect(queue_id, websocket)
    try:
        while True:

            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(queue_id, websocket)

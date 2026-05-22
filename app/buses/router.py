from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import firestore
from typing import List
from app.core.dependencies import get_firestore, verify_token, require_bus_attendant
from app.buses.schema import (
    BusInfo,
    BusInfoResponse,
    BusInfoUpdate,
    ClaimBusResponse,
    BusLocationUpdate,
    PrivilegedAddRequest,
    QRScanRequest,
)
from app.buses.service import BusService
from app.core.qr_service import QRService
from app.queues.service import QueueService

router = APIRouter(prefix="/buses", tags=["buses"])


def get_bus_service(db: firestore.Client = Depends(get_firestore)) -> BusService:
    return BusService(db)


@router.post("/")
def create_bus(
    bus_info: BusInfo,
    bus_service: BusService = Depends(get_bus_service),
):
    bus_data = bus_info.dict()
    bus_id = bus_service.create_bus(bus_data)
    return {"id": bus_id, "message": "Bus info created successfully"}


@router.get("/", response_model=List[BusInfoResponse])
def get_all_buses(
    bus_service: BusService = Depends(get_bus_service),
):
    return bus_service.get_all_buses()


@router.get("/available", response_model=List[BusInfoResponse])
def get_available_buses(
    bus_service: BusService = Depends(get_bus_service),
):
    return bus_service.get_available_buses()


@router.get("/{bus_id}", response_model=BusInfoResponse)
def get_bus(
    bus_id: str,
    bus_service: BusService = Depends(get_bus_service),
):
    return bus_service.get_bus_by_id(bus_id)


@router.put("/{bus_id}", response_model=BusInfoResponse)
def update_bus(
    bus_id: str,
    bus_update: BusInfoUpdate,
    bus_service: BusService = Depends(get_bus_service),
):
    update_data = bus_update.to_update_dict()
    return bus_service.update_bus(bus_id, update_data)


@router.post("/{bus_id}/claim", response_model=ClaimBusResponse)
def claim_bus(
    bus_id: str,
    bus_service: BusService = Depends(get_bus_service),
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
):
    return bus_service.claim_bus(bus_id, uid, attendant_profile)


@router.post("/{bus_id}/release", response_model=ClaimBusResponse)
def release_bus(
    bus_id: str,
    bus_service: BusService = Depends(get_bus_service),
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
):
    return bus_service.release_bus(bus_id, uid, attendant_profile)


@router.get("/attendant/my-bus", response_model=BusInfoResponse)
def get_my_bus(
    bus_service: BusService = Depends(get_bus_service),
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
):
    return bus_service.get_my_bus(uid)


@router.post("/{bus_id}/arrive")
def bus_arrival(
    bus_id: str,
    bus_service: BusService = Depends(get_bus_service),
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
):
    return bus_service.mark_bus_arrival(bus_id, uid)


@router.post("/{bus_id}/location")
def update_bus_location(
    bus_id: str,
    location: BusLocationUpdate,
    bus_service: BusService = Depends(get_bus_service),
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
):
    return bus_service.update_bus_location(bus_id, uid, location.lat, location.lon)


@router.post("/{bus_id}/scan-qr")
async def scan_qr_code(
    bus_id: str,
    body: QRScanRequest,
    bus_service: BusService = Depends(get_bus_service),
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
):
    qr_service = QRService()
    queue_service = QueueService(db)

    try:
        payload = qr_service.decrypt_token_wrapper(body.qr_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or tampered QR code")

    result = await bus_service.scan_qr_and_board(bus_id, payload, queue_service)

    return result


@router.post("/{bus_id}/depart")
async def depart_bus(
    bus_id: str,
    bus_service: BusService = Depends(get_bus_service),
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
):
    return await bus_service.mark_bus_departure(bus_id, uid)


@router.post("/{bus_id}/finish-trip")
def finish_trip(
    bus_id: str,
    bus_service: BusService = Depends(get_bus_service),
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
):
    return bus_service.finish_trip(bus_id, uid)


@router.get("/attendant/passengers")
def get_passenger_list(
    bus_service: BusService = Depends(get_bus_service),
    queue_service: QueueService = Depends(lambda: QueueService(get_firestore())),
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
):
    return bus_service.get_attendant_passenger_list(uid, queue_service)


@router.post("/{bus_id}/manual-add")
def add_manual_passenger(
    bus_id: str,
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
    bus_service: BusService = Depends(get_bus_service),
    queue_service: QueueService = Depends(lambda: QueueService(get_firestore())),
):
    """
    Adds a Walk-in passenger automatically to the current bus queue.
    Ticket numbers loop back after trip completion.
    """
    bus_ref = bus_service.db.collection("buses").document(bus_id)
    bus_snapshot = bus_ref.get()

    if not bus_snapshot.exists:
        raise HTTPException(status_code=404, detail="Bus not found")

    bus = bus_snapshot.to_dict()
    queue_id = bus.get("current_queue_id")

    if not queue_id:
        raise HTTPException(status_code=400, detail="No active queue for this bus")

    capacity = bus.get("capacity", 0)

    queue_ref = bus_service.db.collection("queues").document(queue_id)
    passengers_ref = queue_ref.collection("passengers")

    passengers = [p.to_dict() for p in passengers_ref.stream()]
    total_boarded = len(passengers)

    if total_boarded >= capacity:
        raise HTTPException(status_code=400, detail="Bus capacity reached")

    numbers = []
    for p in passengers:
        name = p.get("full_name", "")
        if name.startswith("Walk-in #"):
            try:
                numbers.append(int(name.split("#")[1]))
            except:
                continue

    next_number = max(numbers, default=0) + 1
    if next_number > 9999:
        next_number = 1

    walkin_name = f"Walk-in #{next_number:04d}"

    queue_data = queue_ref.get().to_dict()
    ticket_number = queue_data.get("next_ticket", 1)

    passengers_ref.document(str(ticket_number)).set(
        {
            "user_id": walkin_name,
            "full_name": walkin_name,
            "status": "boarded",
            "ticket_number": ticket_number,
            "is_privileged": False,
            "joined_at": firestore.SERVER_TIMESTAMP,
            "added_by": uid,
        }
    )

    queue_ref.update({"next_ticket": ticket_number + 1})

    return {
        "message": "Walk-in passenger added",
        "passenger": {
            "user_id": walkin_name,
            "full_name": walkin_name,
            "ticket_number": ticket_number,
            "added_by": uid,
        },
    }


@router.post("/{bus_id}/manual-add/privileged")
def add_manual_privileged_passenger(
    bus_id: str,
    body: PrivilegedAddRequest,
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
    bus_service: BusService = Depends(get_bus_service),
):
    bus_ref = bus_service.db.collection("buses").document(bus_id)
    bus_snapshot = bus_ref.get()

    if not bus_snapshot.exists:
        raise HTTPException(status_code=404, detail="Bus not found")

    bus = bus_snapshot.to_dict()
    queue_id = bus.get("current_queue_id")

    if not queue_id:
        raise HTTPException(status_code=400, detail="No active queue for this bus")

    capacity = bus.get("capacity", 0)
    priority_limit = bus.get("priority_seat", 0)

    queue_ref = bus_service.db.collection("queues").document(queue_id)
    passengers_ref = queue_ref.collection("passengers")

    passengers = [p.to_dict() for p in passengers_ref.stream()]
    total_boarded = len(passengers)
    privileged_boarded = sum(1 for p in passengers if p.get("is_privileged"))

    if total_boarded >= capacity:
        raise HTTPException(status_code=400, detail="Bus capacity reached")

    if priority_limit == 0 and not body.force:
        return {
            "success": False,
            "code": "NO_PRIORITY_SEATS",
            "message": "This bus has no priority seats",
            "can_force": True,
        }

    if privileged_boarded >= priority_limit and not body.force:
        return {
            "success": False,
            "code": "PRIORITY_SEATS_FULL",
            "message": "No more priority seats available",
            "can_force": True,
        }

    numbers = []
    for p in passengers:
        name = p.get("full_name", "")
        if name.startswith("Priority Walk-in #"):
            try:
                numbers.append(int(name.split("#")[1]))
            except:
                continue

    next_number = max(numbers, default=0) + 1
    if next_number > 9999:
        next_number = 1

    walkin_name = f"Priority Walk-in #{next_number:04d}"

    queue_data = queue_ref.get().to_dict()
    ticket_number = queue_data.get("next_ticket", 1)

    passengers_ref.document(str(ticket_number)).set(
        {
            "user_id": walkin_name,
            "full_name": walkin_name,
            "status": "boarded",
            "ticket_number": ticket_number,
            "is_privileged": True,
            "joined_at": firestore.SERVER_TIMESTAMP,
            "added_by": uid,
        }
    )

    queue_ref.update({"next_ticket": ticket_number + 1})

    return {
        "success": True,
        "message": "Privileged passenger added",
        "ticket_number": ticket_number,
        "forced": body.force,
        "remaining_priority_seats": max(priority_limit - privileged_boarded - 1, 0),
        "remaining_capacity": capacity - total_boarded - 1,
    }


@router.get("/attendant/trips")
def get_attendant_trips(
    bus_service: BusService = Depends(get_bus_service),
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
):
    return bus_service.get_attendant_trip_history(uid)


@router.get("/attendant/trips/{trip_id}")
def get_attendant_trip_detail(
    trip_id: str,
    bus_service: BusService = Depends(get_bus_service),
    uid: str = Depends(verify_token),
    attendant_profile: dict = Depends(require_bus_attendant),
):
    return bus_service.get_attendant_trip_detail(uid, trip_id)

from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import firestore
from app.core.dependencies import get_firestore
from app.buses.schema import BusInfo, BusInfoResponse

router = APIRouter(prefix="/buses", tags=["buses"])


@router.post("/")
def create_bus(
    bus_info: BusInfo,
    db: firestore.Client = Depends(get_firestore),
):
    bus_ref = db.collection("buses").document()
    geo_point = None
    if bus_info.current_location:
        geo_point = firestore.GeoPoint(
            bus_info.current_location.lat, bus_info.current_location.lon
        )

    bus_data = {
        "id": bus_ref.id,
        "plate_number": bus_info.plate_number,
        "priority_seat": bus_info.priority_seat,
        "capacity": bus_info.capacity,
        "status": bus_info.status,
        "current_location": geo_point,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    bus_ref.set(bus_data)
    return {"id": bus_ref.id, "message": "Bus iinfo created successfully"}


@router.get("/{bus_id}", response_model=BusInfoResponse)
def get_bus(
    bus_id: str,
    db: firestore.Client = Depends(get_firestore),
):
    bus_ref = db.collection("buses").document(bus_id)
    bus_snapshot = bus_ref.get()
    if not bus_snapshot.exists:
        raise HTTPException(status_code=404, detail="Bus not found")

    data = bus_snapshot.to_dict()

    if isinstance(data.get("current_location"), firestore.GeoPoint):
        data["current_location"] = {
            "lat": data["current_location"].latitude,
            "lon": data["current_location"].longitude,
        }

    return data

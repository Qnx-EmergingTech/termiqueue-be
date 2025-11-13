from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import firestore
from typing import List
from app.core.dependencies import get_firestore, verify_token, require_bus_attendant
from app.buses.schema import BusInfo, BusInfoResponse, BusInfoUpdate, ClaimBusResponse
from app.buses.service import BusService

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

from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import firestore
from loguru import logger
from app.core.dependencies import get_firestore, verify_token
from app.geofence.service import GeofenceService
from app.geofence.schema import GeofenceConfig

router = APIRouter(prefix="/geofence", tags=["geofence"])


def get_geofence_service(
    db: firestore.Client = Depends(get_firestore),
) -> GeofenceService:
    return GeofenceService(db)


@router.get("/", response_model=GeofenceConfig)
def get_geofence_config(
    service: GeofenceService = Depends(get_geofence_service),
):
    config = service.get_geofence()
    logger.info(
        f"Geofence config fetched — lat={config.lat} lon={config.lon} radius={config.radius_meters}m"
    )
    return config


@router.put("/")
def update_geofence_config(
    config: GeofenceConfig,
    service: GeofenceService = Depends(get_geofence_service),
    uid: str = Depends(verify_token),
):
    profile_ref = service.db.collection("profiles").document(uid)
    profile_snapshot = profile_ref.get()

    if not profile_snapshot.exists:
        logger.warning(f"Geofence update failed — profile not found for uid={uid}")
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = profile_snapshot.to_dict()

    if profile.get("user_type") != "admin":
        logger.warning(f"Geofence update denied — uid={uid} is not an admin")
        raise HTTPException(
            status_code=403,
            detail="Only admin users can update geofence configuration",
        )

    service.update_geofence(config)
    logger.info(
        f"Geofence updated by uid={uid} — lat={config.lat} lon={config.lon} radius={config.radius_meters}m"
    )
    return {"message": "Geofence updated successfully"}


@router.get("/destination")
def list_destination_geofence_configs(
    service: GeofenceService = Depends(get_geofence_service),
):
    configs = service.list_destination_geofences()
    logger.info(f"Destination geofence configs fetched — count={len(configs)}")
    return configs


@router.get("/destination/{destination}", response_model=GeofenceConfig)
def get_destination_geofence_config(
    destination: str,
    service: GeofenceService = Depends(get_geofence_service),
):
    config = service.get_destination_geofence(destination)

    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Destination geofence has not been configured for '{destination}'",
        )

    logger.info(
        f"Destination geofence config fetched — destination={destination} lat={config.lat} lon={config.lon} radius={config.radius_meters}m"
    )
    return config


@router.put("/destination/{destination}")
def update_destination_geofence_config(
    destination: str,
    config: GeofenceConfig,
    service: GeofenceService = Depends(get_geofence_service),
    uid: str = Depends(verify_token),
):
    profile_ref = service.db.collection("profiles").document(uid)
    profile_snapshot = profile_ref.get()

    if not profile_snapshot.exists:
        logger.warning(
            f"Destination geofence update failed — profile not found for uid={uid}"
        )
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = profile_snapshot.to_dict()

    if profile.get("user_type") != "admin":
        logger.warning(
            f"Destination geofence update denied — uid={uid} is not an admin"
        )
        raise HTTPException(
            status_code=403,
            detail="Only admin users can update geofence configuration",
        )

    service.update_destination_geofence(destination, config)
    logger.info(
        f"Destination geofence updated by uid={uid} — destination={destination} lat={config.lat} lon={config.lon} radius={config.radius_meters}m"
    )
    return {"message": "Destination geofence updated successfully"}

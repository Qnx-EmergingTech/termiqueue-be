from firebase_admin import firestore
from loguru import logger
from app.core.config import AYALA_LAT, AYALA_LON, GEOFENCE_RADIUS_METERS
from app.geofence.schema import GeofenceConfig


class GeofenceService:
    CONFIG_COLLECTION = "config"
    CONFIG_DOC = "geofence"

    def __init__(self, db: firestore.Client):
        self.db = db

    def get_geofence(self) -> GeofenceConfig:
        ref = self.db.collection(self.CONFIG_COLLECTION).document(self.CONFIG_DOC)
        snap = ref.get()

        if not snap.exists:
            logger.warning("Geofence config not found in Firestore — using defaults")
            return GeofenceConfig(
                lat=AYALA_LAT,
                lon=AYALA_LON,
                radius_meters=GEOFENCE_RADIUS_METERS,
            )

        data = snap.to_dict() or {}

        try:
            config = GeofenceConfig(
                lat=data.get("lat", AYALA_LAT),
                lon=data.get("lon", AYALA_LON),
                radius_meters=data.get("radius_meters", GEOFENCE_RADIUS_METERS),
            )
            return config
        except Exception as e:
            logger.error(f"Geofence config parse error — falling back to defaults: {e}")
            return GeofenceConfig(
                lat=AYALA_LAT,
                lon=AYALA_LON,
                radius_meters=GEOFENCE_RADIUS_METERS,
            )

    def update_geofence(self, config: GeofenceConfig):
        ref = self.db.collection(self.CONFIG_COLLECTION).document(self.CONFIG_DOC)
        ref.set(
            {
                "lat": config.lat,
                "lon": config.lon,
                "radius_meters": config.radius_meters,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        logger.info(
            f"Geofence config saved to Firestore — lat={config.lat} lon={config.lon} radius={config.radius_meters}m"
        )

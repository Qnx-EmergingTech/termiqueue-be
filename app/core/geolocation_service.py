import math
from app.geofence.service import GeofenceService
from firebase_admin import firestore

# AYALA_LAT = 14.550549131986589
# AYALA_LON = 121.02787825354999
# GEOFENCE_RADIUS_METERS = 200


class GeolocationService:
    def __init__(self, db: firestore.Client):
        self.geofence_service = GeofenceService(db)
        config = self.geofence_service.get_geofence()

        self.lat = config.lat
        self.lon = config.lon
        self.geofence_radius_meters = config.radius_meters

    def haversine(self, user_lat: float, user_lon: float) -> float:
        EARTH_RADIUS_METERS = 6371000
        phi1, phi2 = math.radians(user_lat), math.radians(self.lat)
        dphi = math.radians(self.lat - user_lat)
        dlambda = math.radians(self.lon - user_lon)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return EARTH_RADIUS_METERS * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def is_within_geofence(self, user_lat: float, user_lon: float) -> bool:
        distance = self.haversine(user_lat, user_lon)
        return distance <= self.geofence_radius_meters

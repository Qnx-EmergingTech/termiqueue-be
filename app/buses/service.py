from fastapi import HTTPException
from firebase_admin import firestore


class BusService:
    def __init__(self, db: firestore.Client):
        self.db = db

    def create_bus(self, bus_data):
        bus_ref = self.db.collection("buses").document()

        geo_point = None
        if bus_data.get("current_location"):
            geo_point = firestore.GeoPoint(
                bus_data["current_location"]["lat"], bus_data["current_location"]["lon"]
            )

        bus_doc = {
            "id": bus_ref.id,
            "plate_number": bus_data["plate_number"],
            "priority_seat": bus_data["priority_seat"],
            "capacity": bus_data["capacity"],
            "destination": bus_data.get("destination"),
            "status": bus_data.get("status", "available"),
            "current_location": geo_point,
            "attendant_id": bus_data.get("attendant_id"),
            "attendant_name": bus_data.get("attendant_name"),
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        bus_ref.set(bus_doc)
        return bus_ref.id

    def get_all_buses(self):
        buses_ref = self.db.collection("buses").stream()
        buses = []

        for bus_snapshot in buses_ref:
            data = bus_snapshot.to_dict()
            data = self._convert_geopoint_to_location(data)
            buses.append(data)

        return buses

    def get_available_buses(self):
        buses_ref = (
            self.db.collection("buses").where("status", "==", "available").stream()
        )
        buses = []

        for bus_snapshot in buses_ref:
            data = bus_snapshot.to_dict()
            data = self._convert_geopoint_to_location(data)
            buses.append(data)

        return buses

    def get_bus_by_id(self, bus_id: str):
        bus_ref = self.db.collection("buses").document(bus_id)
        bus_snapshot = bus_ref.get()

        if not bus_snapshot.exists:
            raise HTTPException(status_code=404, detail="Bus not found")

        data = bus_snapshot.to_dict()
        return self._convert_geopoint_to_location(data)

    def update_bus(self, bus_id: str, update_data):
        bus_ref = self.db.collection("buses").document(bus_id)
        bus_snapshot = bus_ref.get()

        if not bus_snapshot.exists:
            raise HTTPException(status_code=404, detail="Bus not found")

        if "current_location" in update_data and update_data["current_location"]:
            geo_point = firestore.GeoPoint(
                update_data["current_location"]["lat"],
                update_data["current_location"]["lon"],
            )
            update_data["current_location"] = geo_point

        update_data["updated_at"] = firestore.SERVER_TIMESTAMP
        bus_ref.update(update_data)

        updated_bus = bus_ref.get().to_dict()
        return self._convert_geopoint_to_location(updated_bus)

    def claim_bus(self, bus_id: str, uid: str, attendant_profile):
        bus_ref = self.db.collection("buses").document(bus_id)
        bus_snapshot = bus_ref.get()

        if not bus_snapshot.exists:
            raise HTTPException(status_code=404, detail="Bus not found")

        bus_data = bus_snapshot.to_dict()

        if bus_data.get("attendant_id") and bus_data.get("status") == "active":
            raise HTTPException(
                status_code=400,
                detail=f"Bus is already claimed by attendant: {bus_data.get('attendant_name')}",
            )

        if bus_data.get("status") not in ["available", None]:
            raise HTTPException(
                status_code=400,
                detail=f"Bus is not available. Current status: {bus_data.get('status')}",
            )

        attendant_name = f"{attendant_profile.get('first_name')} {attendant_profile.get('last_name')}"

        bus_ref.update(
            {
                "attendant_id": uid,
                "attendant_name": attendant_name,
                "status": "active",
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

        return {
            "id": bus_id,
            "message": "Bus claimed successfully",
            "attendant_id": uid,
            "attendant_name": attendant_name,
        }

    def release_bus(self, bus_id: str, uid: str, attendant_profile):
        bus_ref = self.db.collection("buses").document(bus_id)
        bus_snapshot = bus_ref.get()

        if not bus_snapshot.exists:
            raise HTTPException(status_code=404, detail="Bus not found")

        bus_data = bus_snapshot.to_dict()

        if bus_data.get("attendant_id") != uid:
            raise HTTPException(
                status_code=403, detail="You are not assigned to this bus"
            )

        attendant_name = f"{attendant_profile.get('first_name')} {attendant_profile.get('last_name')}"

        bus_ref.update(
            {
                "attendant_id": None,
                "attendant_name": None,
                "status": "available",
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

        return {
            "id": bus_id,
            "message": "Bus released successfully",
            "attendant_id": uid,
            "attendant_name": attendant_name,
        }

    def get_my_bus(self, uid: str):
        buses_ref = (
            self.db.collection("buses")
            .where("attendant_id", "==", uid)
            .limit(1)
            .stream()
        )

        for bus_snapshot in buses_ref:
            data = bus_snapshot.to_dict()
            return self._convert_geopoint_to_location(data)

        raise HTTPException(status_code=404, detail="You are not assigned to any bus")

    def _convert_geopoint_to_location(self, data):
        if isinstance(data.get("current_location"), firestore.GeoPoint):
            data["current_location"] = {
                "lat": data["current_location"].latitude,
                "lon": data["current_location"].longitude,
            }
        return data

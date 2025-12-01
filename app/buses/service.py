from fastapi import HTTPException
from firebase_admin import firestore
from datetime import datetime


class BusService:
    def __init__(self, db: firestore.Client):
        self.db = db

    def create_bus(self, bus_data):
        existing = (
            self.db.collection("buses")
            .where("plate_number", "==", bus_data["plate_number"])
            .limit(1)
            .stream()
        )

        for _ in existing:
            raise HTTPException(
                status_code=409,
                detail="A bus with this plate number is already registered",
            )

        bus_ref = self.db.collection("buses").document()

        geo_point = None
        if bus_data.get("current_location"):
            geo_point = firestore.GeoPoint(
                bus_data["current_location"]["lat"], bus_data["current_location"]["lon"]
            )

        bus_doc = {
            "id": bus_ref.id,
            "plate_number": bus_data["plate_number"],
            "bus_name": bus_data["bus_name"],
            "bus_number": bus_data["bus_number"],
            "priority_seat": bus_data["priority_seat"],
            "capacity": bus_data["capacity"],
            "origin": bus_data["origin"],
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

    def update_bus_location(self, bus_id: str, uid: str, lat: float, lon: float):
        bus_ref = self.db.collection("buses").document(bus_id)
        bus_snapshot = bus_ref.get()

        if not bus_snapshot.exists:
            raise HTTPException(status_code=404, detail="Bus not found")

        bus_data = bus_snapshot.to_dict()

        if bus_data.get("status") != "active":
            raise HTTPException(status_code=400, detail="Bus is not active")

        if bus_data.get("attendant_id") != uid:
            raise HTTPException(
                status_code=403,
                detail="You are not the assigned attendant for this bus",
            )

        geo_point = firestore.GeoPoint(lat, lon)

        bus_ref.update(
            {
                "current_location": geo_point,
                "last_location_update": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

        return {
            "id": bus_id,
            "message": "Location updated successfully",
            "current_location": {"lat": lat, "lon": lon},
        }

    def mark_bus_arrival(self, bus_id: str, uid: str):
        bus_ref = self.db.collection("buses").document(bus_id)
        bus_snapshot = bus_ref.get()

        if not bus_snapshot.exists:
            raise HTTPException(status_code=404, detail="Bus not found")

        bus = bus_snapshot.to_dict()

        if bus.get("attendant_id") != uid:
            raise HTTPException(
                status_code=403,
                detail="You are not the assigned attendant for this bus",
            )

        destination = bus.get("destination")
        if not destination:
            raise HTTPException(
                status_code=400, detail="Bus does not have an assigned destination"
            )

        if bus.get("status") == "arrived":
            return {
                "message": "Bus is already marked as arrived",
                "queue_updated": False,
                "queue_id": bus.get("current_queue_id"),
            }

        queue_query = (
            self.db.collection("queues")
            .where("destination", "==", destination)
            .where("status", "==", None)
            .limit(1)
            .stream()
        )

        queue_docs = list(queue_query)
        queue_updated = False
        queue_id = None

        if queue_docs:
            queue_snapshot = queue_docs[0]
            queue_ref = queue_snapshot.reference
            queue_id = queue_snapshot.id

            queue_ref.update(
                {
                    "status": "boarding",
                    "bus_id": bus_id,
                    "capacity": bus.get("capacity"),
                    "priority_seat": bus.get("priority_seat"),
                    "updated_at": firestore.SERVER_TIMESTAMP,
                }
            )

            queue_updated = True

        bus_ref.update(
            {
                "status": "arrived",
                "arrived_at": firestore.SERVER_TIMESTAMP,
                "current_queue_id": queue_id,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

        return {
            "message": "Bus arrival recorded",
            "queue_updated": queue_updated,
            "queue_id": queue_id,
        }

    def scan_qr_and_board(self, bus_id: str, payload: dict, queue_service):
        user_id = payload.get("user_id")
        full_name = payload.get("full_name")
        queue_id = payload.get("queue_id")
        ticket_number = payload.get("ticket_number")

        if not (user_id and queue_id and ticket_number):
            raise HTTPException(status_code=400, detail="Malformed QR payload")

        bus_ref = self.db.collection("buses").document(bus_id)
        bus_snapshot = bus_ref.get()
        if not bus_snapshot.exists:
            raise HTTPException(status_code=404, detail="Bus not found")

        bus = bus_snapshot.to_dict()

        if bus.get("attendant_id") is None:
            raise HTTPException(status_code=403, detail="Bus has no assigned attendant")

        current_queue_id = bus.get("current_queue_id")
        if current_queue_id != queue_id:
            raise HTTPException(
                status_code=400, detail="Passenger belongs to a different queue"
            )

        queue_ref = self.db.collection("queues").document(queue_id)
        passenger_ref = queue_ref.collection("passengers").document(str(ticket_number))
        passenger_snapshot = passenger_ref.get()

        if not passenger_snapshot.exists:
            raise HTTPException(status_code=404, detail="Passenger not found in queue")

        passenger = passenger_snapshot.to_dict()

        if passenger.get("user_id") != user_id:
            raise HTTPException(
                status_code=400, detail="QR does not match passenger entry"
            )

        if passenger.get("status") == "boarded":
            raise HTTPException(status_code=400, detail="Passenger already boarded")

        passenger_ref.update(
            {
                "status": "boarded",
                "boarded_at": firestore.SERVER_TIMESTAMP,
            }
        )

        bus_ref.update(
            {
                "boarded_count": firestore.Increment(1),
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

        profile_ref = self.db.collection("profiles").document(user_id)
        profile_ref.update({"in_queue": False})

        return {
            "message": "Passenger boarded successfully",
            "passenger": {
                "user_id": user_id,
                "full_name": full_name,
                "ticket_number": ticket_number,
                "is_privileged": passenger.get("is_privileged", False),
                "status": "boarded",
            },
        }

from fastapi import HTTPException
from firebase_admin import firestore
from datetime import datetime, timedelta, timezone
from app.core.geolocation_service import GeolocationService
from app.core.notification_service import NotificationService
from firebase_admin import firestore
from app.core.ws_manager import ws_manager
from app.core.ws_events import PASSENGER_BOARDED
from app.core.ws_events import BUS_DEPARTED


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

    def _is_under_coding(self, plate_number: str) -> bool:
        coding_schedule = {
            0: {"1", "2"},  # Monday
            1: {"3", "4"},  # Tuesday
            2: {"5", "6"},  # Wednesday
            3: {"7", "8"},  # Thursday
            4: {"9", "0"},  # Friday
        }
        ph_tz = timezone(timedelta(hours=8))
        today = datetime.now(ph_tz).weekday()
        if today not in coding_schedule:
            return False
        last_digit = plate_number.strip()[-1]
        return last_digit in coding_schedule[today]

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

        if self._is_under_coding(bus_data.get("plate_number", "")):
            raise HTTPException(
                status_code=403,
                detail=f"Vehicle {bus_data.get('bus_name')} with plate number {bus_data.get('plate_number')} is under coding today and cannot be claimed.",
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

        self._check_geofence_and_notify(bus_data, lat, lon)

        return {
            "id": bus_id,
            "message": "Location updated successfully",
            "current_location": {"lat": lat, "lon": lon},
        }

    def _check_geofence_and_notify(self, bus_data, lat, lon):
        geofence = GeolocationService()
        notifier = NotificationService()

        bus_id = bus_data["id"]
        destination = bus_data.get("destination")

        if not destination:
            return

        if bus_data.get("last_proximity_notification_sent"):
            return

        if not geofence.is_within_geofence(lat, lon):
            return

        queue_query = (
            self.db.collection("queues")
            .where("destination", "==", destination)
            .where("status", "==", "waiting")
            .limit(1)
            .stream()
        )

        queue_docs = list(queue_query)
        if not queue_docs:
            return

        queue_ref = queue_docs[0].reference

        passengers = (
            queue_ref.collection("passengers").where("status", "==", "waiting").stream()
        )

        user_ids = [
            p.to_dict().get("user_id") for p in passengers if p.to_dict().get("user_id")
        ]

        if not user_ids:
            return

        for user_id in user_ids:
            profile = self.db.collection("profiles").document(user_id).get().to_dict()
            token = profile.get("fcm_token") if profile else None

            if not token:
                continue

            notifier.send_to_token(
                token=token,
                title="Your bus is approaching!",
                body="Your bus is nearing Ayala Terminal. Please prepare for boarding.",
            )

        self.db.collection("buses").document(bus_id).update(
            {"last_proximity_notification_sent": firestore.SERVER_TIMESTAMP}
        )

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
                status_code=400,
                detail="Bus does not have an assigned destination",
            )

        if bus.get("status") == "arrived":
            return {
                "message": "Bus already marked as arrived",
                "queue_id": bus.get("current_queue_id"),
            }

        queue_query = (
            self.db.collection("queues")
            .where("destination", "==", destination)
            .limit(1)
            .stream()
        )

        queue_docs = list(queue_query)

        if not queue_docs:
            bus_ref.update(
                {
                    "status": "arrived",
                    "arrived_at": firestore.SERVER_TIMESTAMP,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                }
            )
            return {
                "message": "Bus arrived but no waiting queue found",
                "queue_id": None,
            }

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

        bus_ref.update(
            {
                "status": "arrived",
                "arrived_at": firestore.SERVER_TIMESTAMP,
                "current_queue_id": queue_id,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

        notifier = NotificationService()

        waiting_passengers = (
            queue_ref.collection("passengers").where("status", "==", "waiting").stream()
        )

        for p in waiting_passengers:
            passenger = p.to_dict()
            user_id = passenger.get("user_id")
            ticket_number = passenger.get("ticket_number")

            if not user_id or ticket_number is None:
                continue

            profile = self.db.collection("profiles").document(user_id).get().to_dict()

            token = profile.get("fcm_token") if profile else None
            if not token:
                continue

            notifier.send_to_token(
                token=token,
                title="Your bus has arrived!",
                body=f"Please proceed to boarding. Your queue number is {ticket_number}.",
            )

        return {
            "message": "Bus arrival recorded and passengers notified",
            "queue_id": queue_id,
        }

    async def scan_qr_and_board(self, bus_id: str, payload: dict, queue_service):
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

        if bus.get("current_queue_id") != queue_id:
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

        if passenger.get("status") in ("boarded", "ongoing"):
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

        self.db.collection("profiles").document(user_id).update(
            {"in_queue": False, "in_queue_date": None}
        )

        await ws_manager.broadcast(
            queue_id,
            {
                "type": PASSENGER_BOARDED,
                "payload": {
                    "user_id": user_id,
                    "full_name": full_name,
                    "ticket_number": ticket_number,
                    "status": "boarded",
                    "is_privileged": passenger.get("is_privileged", False),
                },
            },
        )

        return {"message": "Passenger boarded successfully"}

    async def mark_bus_departure(self, bus_id: str, uid: str):
        MIN_PASSENGERS = 5

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

        queue_id = bus.get("current_queue_id")
        if not queue_id:
            raise HTTPException(
                status_code=400, detail="Bus is not linked to any queue"
            )

        queue_ref = self.db.collection("queues").document(queue_id)

        boarded_passengers = list(
            queue_ref.collection("passengers").where("status", "==", "boarded").stream()
        )

        if len(boarded_passengers) < MIN_PASSENGERS:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot start trip. Minimum {MIN_PASSENGERS} passengers required.",
            )

        batch = self.db.batch()
        for p in boarded_passengers:
            batch.update(p.reference, {"status": "ongoing"})
        batch.commit()

        departed_at = datetime.utcnow()

        bus_ref.update(
            {
                "status": "in_transit",
                "departed_at": departed_at,
                "boarded_count": 0,
                "last_proximity_notification_sent": None,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

        await ws_manager.broadcast(
            queue_id,
            {
                "type": BUS_DEPARTED,
                "payload": {
                    "bus_id": bus_id,
                    "departed_at": departed_at.isoformat(),
                    "boarded_count": len(boarded_passengers),
                    "passenger_status": "ongoing",
                },
            },
        )

        return {
            "message": "Bus departure recorded",
            "bus_id": bus_id,
            "queue_id": queue_id,
            "boarded_count": len(boarded_passengers),
        }

    def finish_trip(self, bus_id: str, uid: str):
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

        if bus.get("status") != "in_transit":
            raise HTTPException(
                status_code=400,
                detail="Bus is not in transit",
            )

        queue_id = bus.get("current_queue_id")
        if not queue_id:
            raise HTTPException(
                status_code=400,
                detail="No queue linked to this bus",
            )

        departed_at = bus.get("departed_at")
        if not departed_at:
            raise HTTPException(
                status_code=400,
                detail="Departure time not recorded. Ensure bus has departed before finishing trip.",
            )

        now = datetime.utcnow()

        queue_ref = self.db.collection("queues").document(queue_id)
        passengers_ref = queue_ref.collection("passengers")

        queue_data = queue_ref.get().to_dict() or {}
        destination = queue_data.get("destination")

        ongoing_passengers = list(
            passengers_ref.where("status", "==", "ongoing").stream()
        )

        batch = self.db.batch()

        for p in ongoing_passengers:
            passenger = p.to_dict()
            user_id = passenger.get("user_id")

            trip_ref = self.db.collection("trips").document()

            batch.set(
                trip_ref,
                {
                    "user_id": user_id,
                    "full_name": passenger.get("full_name"),
                    "bus_id": bus_id,
                    "attendant_id": uid,
                    "bus_number": bus.get("bus_number"),
                    "plate_number": bus.get("plate_number"),
                    "origin": bus.get("origin"),
                    "destination": destination,
                    "queue_id": queue_id,
                    "ticket_number": passenger.get("ticket_number"),
                    "is_privileged": passenger.get("is_privileged", False),
                    "boarded_at": passenger.get("boarded_at"),
                    "departed_at": departed_at,
                    "finished_at": now,
                    "created_at": now,
                },
            )

            batch.delete(p.reference)

        waiting_passengers = list(
            passengers_ref.where("status", "==", "waiting").stream()
        )
        waiting_count = len(waiting_passengers)

        batch.update(
            queue_ref,
            {
                "status": "done" if waiting_count == 0 else "waiting",
                "remaining_passengers": waiting_count,
                "bus_id": None,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
        )

        batch.commit()

        bus_ref.update(
            {
                "status": "available",
                "attendant_id": None,
                "attendant_name": None,
                "current_queue_id": None,
                "finished_at": now,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

        return {
            "message": "Trip finished successfully",
            "bus_id": bus_id,
            "queue_id": queue_id,
            "finished_at": now.isoformat(),
            "passengers_recorded": len(ongoing_passengers),
            "remaining_waiting_passengers": waiting_count,
            "queue_status": "done" if waiting_count == 0 else "waiting",
        }

    def get_attendant_passenger_list(self, uid: str, queue_service):
        buses = (
            self.db.collection("buses")
            .where("attendant_id", "==", uid)
            .limit(1)
            .stream()
        )

        bus = None
        for b in buses:
            bus = b.to_dict()

        if not bus:
            raise HTTPException(
                status_code=404, detail="You are not assigned to any bus"
            )

        bus_id = bus["id"]
        capacity = bus.get("capacity", 0)
        queue_id = bus.get("current_queue_id")

        if not queue_id:
            return {
                "bus_id": bus_id,
                "capacity": capacity,
                "total_onboard": 0,
                "passengers": [],
                "last_passenger_scanned": None,
            }

        q_ref = self.db.collection("queues").document(queue_id)
        passenger_snapshots = q_ref.collection("passengers").stream()

        passengers_list = []
        total_onboard = 0
        last_scanned = None

        for p in passenger_snapshots:
            data = p.to_dict()

            passengers_list.append(
                {
                    "id": data.get("user_id"),
                    "name": data.get("full_name"),
                    "queue_id": queue_id,
                    "status": data.get("status"),
                    "timestamp": data.get("joined_at"),
                }
            )

            if data.get("status") in ("boarded", "ongoing"):
                total_onboard += 1

                boarded_at = data.get("boarded_at")
                if boarded_at:
                    if last_scanned is None or boarded_at > last_scanned["timestamp"]:
                        last_scanned = {
                            "id": data.get("user_id"),
                            "name": data.get("full_name"),
                            "status": data.get("status"),
                            "timestamp": boarded_at,
                        }

        return {
            "bus_id": bus_id,
            "capacity": capacity,
            "total_onboard": total_onboard,
            "passengers": passengers_list,
            "last_passenger_scanned": last_scanned,
        }

    def get_attendant_trip_history(self, uid: str):
        trips_query = (
            self.db.collection("trips").where("attendant_id", "==", uid).stream()
        )

        grouped = {}

        for doc in trips_query:
            data = doc.to_dict()

            key = f"{data.get('bus_id')}_{data.get('departed_at')}"

            if key not in grouped:
                grouped[key] = {
                    "trip_id": key,
                    "bus_id": data.get("bus_id"),
                    "bus_number": data.get("bus_number"),
                    "plate_number": data.get("plate_number"),
                    "origin": data.get("origin"),
                    "destination": data.get("destination"),
                    "departed_at": data.get("departed_at"),
                    "finished_at": data.get("finished_at"),
                    "passenger_count": 0,
                }

            grouped[key]["passenger_count"] += 1

        return {"trips": list(grouped.values())}

    def get_attendant_trip_detail(self, uid: str, trip_id: str):
        try:
            bus_id, departed_at_str = trip_id.split("_", 1)
            departed_at = datetime.fromisoformat(departed_at_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid trip_id format")

        start = departed_at
        end = departed_at + timedelta(seconds=1)

        trips_query = (
            self.db.collection("trips")
            .where("attendant_id", "==", uid)
            .where("bus_id", "==", bus_id)
            .where("departed_at", ">=", start)
            .where("departed_at", "<", end)
            .stream()
        )

        passengers = []

        for doc in trips_query:
            data = doc.to_dict()

            passengers.append(
                {
                    "user_id": data.get("user_id"),
                    "ticket_number": data.get("ticket_number"),
                    "boarded_at": data.get("boarded_at"),
                    "full_name": data.get("full_name"),
                }
            )

        if not passengers:
            raise HTTPException(status_code=404, detail="Trip not found")

        first = passengers[0]

        return {
            "trip_id": trip_id,
            "bus_id": bus_id,
            "bus_number": data.get("bus_number"),
            "plate_number": data.get("plate_number"),
            "origin": data.get("origin"),
            "destination": data.get("destination"),
            "departed_at": data.get("departed_at"),
            "finished_at": data.get("finished_at"),
            "passenger_count": len(passengers),
            "passengers": passengers,
        }

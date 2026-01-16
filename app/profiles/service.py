from firebase_admin import firestore
from typing import Optional
from datetime import datetime


class ProfileService:
    def __init__(self, db: firestore.Client):
        self.db = db

    def get_trip_history(self, user_id: str):
        query = self.db.collection("trips").where("user_id", "==", user_id)

        docs = list(query.stream())

        trips = []

        for doc in docs:
            data = doc.to_dict()
            trips.append(
                {
                    "id": doc.id,
                    "bus_id": data.get("bus_id"),
                    "bus_number": data.get("bus_number"),
                    "plate_number": data.get("plate_number"),
                    "origin": data.get("origin"),
                    "destination": data.get("destination"),
                    "ticket_number": data.get("ticket_number"),
                    "boarded_at": data.get("boarded_at"),
                    "departed_at": data.get("departed_at"),
                }
            )

        return {"trips": trips}

    def get_user_trip_history(
        self,
        user_id: str,
        limit: int = 10,
        start_after_created_at: Optional[datetime] = None,
        start_after_id: Optional[str] = None,
    ):
        query = (
            self.db.collection("trips")
            .where("user_id", "==", user_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .order_by("__name__")
            .limit(limit)
        )

        if start_after_created_at and start_after_id:
            query = query.start_after(
                {
                    "created_at": start_after_created_at,
                    "__name__": start_after_id,
                }
            )

        docs = list(query.stream())

        trips = []
        next_cursor = None

        for doc in docs:
            data = doc.to_dict()
            trips.append(
                {
                    "id": doc.id,
                    "bus_id": data.get("bus_id"),
                    "bus_number": data.get("bus_number"),
                    "plate_number": data.get("plate_number"),
                    "origin": data.get("origin"),
                    "destination": data.get("destination"),
                    "ticket_number": data.get("ticket_number"),
                    "boarded_at": data.get("boarded_at"),
                    "departed_at": data.get("departed_at"),
                }
            )
            next_cursor = {
                "created_at": data.get("created_at"),
                "id": doc.id,
            }

        return {
            "trips": trips,
            "limit": limit,
            "next_cursor": next_cursor,
        }

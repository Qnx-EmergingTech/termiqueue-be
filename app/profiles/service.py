from firebase_admin import firestore
from fastapi import HTTPException


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
                    "finished_at": data.get("finished_at"),
                }
            )

        return {"trips": trips}

    def get_trip_by_id(self, *, user_id: str, trip_id: str):
        trip_ref = self.db.collection("trips").document(trip_id)
        snapshot = trip_ref.get()

        if not snapshot.exists:
            raise HTTPException(status_code=404, detail="Trip not found")

        data = snapshot.to_dict()

        if data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return {
            "id": snapshot.id,
            "bus_id": data.get("bus_id"),
            "bus_number": data.get("bus_number"),
            "plate_number": data.get("plate_number"),
            "origin": data.get("origin"),
            "destination": data.get("destination"),
            "ticket_number": data.get("ticket_number"),
            "boarded_at": data.get("boarded_at"),
            "departed_at": data.get("departed_at"),
            "finished_at": data.get("finished_at"),
        }

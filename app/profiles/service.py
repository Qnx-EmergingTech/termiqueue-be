from firebase_admin import firestore
from fastapi import HTTPException
from loguru import logger


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

        logger.info(f"Trip history fetched for user_id={user_id} count={len(trips)}")
        return {"trips": trips}

    def get_trip_by_id(self, *, user_id: str, trip_id: str):
        trip_ref = self.db.collection("trips").document(trip_id)
        snapshot = trip_ref.get()

        if not snapshot.exists:
            logger.warning(
                f"Trip not found trip_id={trip_id} requested by user_id={user_id}"
            )
            raise HTTPException(status_code=404, detail="Trip not found")

        data = snapshot.to_dict()

        if data.get("user_id") != user_id:
            logger.warning(
                f"Access denied — trip_id={trip_id} does not belong to user_id={user_id}"
            )
            raise HTTPException(status_code=403, detail="Access denied")

        logger.info(f"Trip detail fetched trip_id={trip_id} for user_id={user_id}")
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


class VoucherService:
    def __init__(self, db: firestore.Client):
        self.db = db

    def code_exists(self, code_to_find: str) -> bool:
        query = (
            self.db.collection("voucher_code")
            .where("code", "==", code_to_find)
            .limit(1)  # stop after first match — cheaper
        )
        docs = query.get()
        return len(docs) > 0

    def get_voucher_by_code(self, code_to_find: str):
        docs = (
            self.db.collection("voucher_code")
            .where("code", "==", code_to_find)
            .limit(1)
            .get()
        )
        return docs[0] if docs else None

    def mark_used(self, voucher_doc) -> None:
        voucher_doc.reference.update({"used": True})

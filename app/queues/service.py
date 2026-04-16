from fastapi import HTTPException
from firebase_admin import firestore
from typing import Optional
from app.core.ws_manager import ws_manager
from app.core.ws_events import PASSENGER_QUEUED
from app.core.ws_events import PASSENGER_LEFT


class QueueService:
    def __init__(self, db: firestore.Client):
        self.db = db

    async def join_queue(self, uid: str, queue_id: str):
        MAX_PASSENGERS = 21

        profile_ref = self.db.collection("profiles").document(uid)
        profile_snapshot = profile_ref.get()

        if not profile_snapshot.exists:
            raise HTTPException(status_code=404, detail="Profile not found")

        profile_data = profile_snapshot.to_dict()

        if profile_data.get("in_queue"):
            raise HTTPException(status_code=400, detail="User already in queue")

        is_privileged = profile_data.get("is_privileged", False)
        first_name = profile_data.get("first_name")
        middle_name = profile_data.get("middle_name")
        last_name = profile_data.get("last_name")

        full_name = " ".join(p for p in [first_name, middle_name, last_name] if p)

        queue_ref = self.db.collection("queues").document(queue_id)

        @firestore.transactional
        def transactional_update(transaction, queue_ref):
            snapshot = queue_ref.get(transaction=transaction)
            data = snapshot.to_dict() or {}
            next_ticket = data.get("next_ticket", 1)

            passengers_ref = queue_ref.collection("passengers")

            passengers = list(passengers_ref.stream())

            if len(passengers) >= MAX_PASSENGERS:
                raise HTTPException(
                    status_code=400,
                    detail="Queue is full (maximum 22 passengers)",
                )

            passenger_ref = passengers_ref.document(str(next_ticket))

            transaction.set(
                passenger_ref,
                {
                    "user_id": uid,
                    "full_name": full_name,
                    "status": "waiting",
                    "ticket_number": next_ticket,
                    "is_privileged": is_privileged,
                    "joined_at": firestore.SERVER_TIMESTAMP,
                },
            )

            transaction.set(
                queue_ref,
                {"next_ticket": next_ticket + 1},
                merge=True,
            )

            return next_ticket

        transaction = self.db.transaction()
        ticket_number = transactional_update(transaction, queue_ref)

        profile_ref.set({"in_queue": True}, merge=True)

        await ws_manager.broadcast(
            queue_id,
            {
                "type": PASSENGER_QUEUED,
                "payload": {
                    "user_id": uid,
                    "full_name": full_name,
                    "ticket_number": ticket_number,
                    "is_privileged": is_privileged,
                    "status": "waiting",
                },
            },
        )

        return {
            "ticket_number": ticket_number,
            "message": "Successfully joined queue",
        }

    async def leave_queue(self, uid: str, queue_id: str):
        profile_ref = self.db.collection("profiles").document(uid)
        profile_snapshot = profile_ref.get()
        if not profile_snapshot.exists:
            raise HTTPException(status_code=404, detail="Profile not found")

        profile_data = profile_snapshot.to_dict() or {}
        if not profile_data.get("in_queue", False):
            raise HTTPException(status_code=400, detail="User is not in a queue")

        queue_ref = self.db.collection("queues").document(queue_id)

        passenger_data = {}

        @firestore.transactional
        def transactional_update(transaction, queue_ref):
            passengers = queue_ref.collection("passengers")
            query = passengers.where("user_id", "==", uid).limit(1)
            docs = list(query.stream(transaction=transaction))

            if not docs:
                raise HTTPException(
                    status_code=404, detail="User not found in this queue"
                )

            passenger_doc = docs[0].reference
            nonlocal passenger_data
            passenger_data = docs[0].to_dict()
            transaction.delete(passenger_doc)

        transaction = self.db.transaction()
        transactional_update(transaction, queue_ref)

        profile_ref.set({"in_queue": False}, merge=True)

        await ws_manager.broadcast(
            queue_id,
            {
                "type": PASSENGER_LEFT,
                "payload": {
                    "user_id": uid,
                    "full_name": passenger_data.get("full_name"),
                    "ticket_number": passenger_data.get("ticket_number"),
                    "status": "left",
                },
            },
        )

        return {"message": "User left the queue successfully"}

    def get_queue_status(self, uid: str, queue_id: str):
        queue_ref = self.db.collection("queues").document(queue_id)
        passengers_ref = queue_ref.collection("passengers")

        docs = list(passengers_ref.where("user_id", "==", uid).limit(1).stream())
        if not docs:
            raise HTTPException(status_code=404, detail="User not found in queue")

        my_doc = docs[0]
        my_data = my_doc.to_dict()

        status = my_data.get("status")

        if status != "waiting":
            return {
                "status": status,
                "queue_number": None,
                "ticket_number": my_data.get("ticket_number"),
                "message": f"Passenger is already {status}",
            }

        waiting_passengers = [
            p.to_dict()
            for p in passengers_ref.where("status", "==", "waiting").stream()
        ]

        seniors = [p for p in waiting_passengers if p.get("is_privileged")]
        normals = [p for p in waiting_passengers if not p.get("is_privileged")]

        seniors.sort(key=lambda p: p["ticket_number"])
        normals.sort(key=lambda p: p["ticket_number"])

        priority_seat = queue_ref.get().to_dict().get("priority_seat", 5)

        seated_priorities = seniors[:priority_seat]
        rest = seniors[priority_seat:] + normals
        rest.sort(key=lambda p: p["ticket_number"])

        full_queue = seated_priorities + rest

        queue_map = {p["user_id"]: idx + 1 for idx, p in enumerate(full_queue)}

        return {
            "status": "waiting",
            "queue_number": queue_map.get(uid),
            "ticket_number": my_data.get("ticket_number"),
        }

    def get_queues(self):
        queues_ref = self.db.collection("queues")
        queues = []
        for doc in queues_ref.stream():
            data = doc.to_dict()
            data["id"] = doc.id
            queues.append(data)
        return queues

    def create_terminal_queue(self, destination: str, priority_seat: int):
        queue_ref = self.db.collection("queues").document()
        queue_ref.set(
            {
                "destination": destination,
                "priority_seat": priority_seat,
                "capacity": None,
                "bus_id": None,
                "eta": None,
                "status": None,
                "next_ticket": 1,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )
        return queue_ref.id

    def get_passenger(self, uid: str, queue_id: str) -> dict:
        queue_ref = self.db.collection("queues").document(queue_id)
        passengers_ref = queue_ref.collection("passengers")

        docs = list(passengers_ref.where("user_id", "==", uid).limit(1).stream())
        if not docs:
            raise HTTPException(status_code=404, detail="User not found in queue")

        doc = docs[0]
        data = doc.to_dict() or {}

        try:
            data["ticket_number"] = int(doc.id)
        except ValueError:
            data["ticket_number"] = doc.id

        return data

    async def force_remove_passenger(
        self,
        attendant_uid: str,
        queue_id: str,
        passenger_id: str,
    ):
        queue_ref = self.db.collection("queues").document(queue_id)
        passengers_ref = queue_ref.collection("passengers")

        docs = list(
            passengers_ref.where("user_id", "==", passenger_id).limit(1).stream()
        )

        if not docs:
            raise HTTPException(
                status_code=404,
                detail="Passenger not found in this queue",
            )

        passenger_doc = docs[0]
        passenger_data = passenger_doc.to_dict() or {}
        passenger_ref = passenger_doc.reference
        passenger_ref.delete()
        profile_ref = self.db.collection("profiles").document(passenger_id)
        profile_snapshot = profile_ref.get()

        if profile_snapshot.exists:
            profile_ref.set({"in_queue": False}, merge=True)

        await ws_manager.broadcast(
            queue_id,
            {
                "type": PASSENGER_LEFT,
                "payload": {
                    "user_id": passenger_id,
                    "full_name": passenger_data.get("full_name"),
                    "ticket_number": passenger_data.get("ticket_number"),
                    "status": "force_removed",
                    "removed_by": attendant_uid,
                },
            },
        )
        return {
            "success": True,
            "message": "Passenger force removed successfully",
            "ticket_number": passenger_data.get("ticket_number"),
        }

from fastapi import HTTPException
from firebase_admin import firestore


class QueueService:
    def __init__(self, db: firestore.Client):
        self.db = db

    def join_queue(self, uid: str, queue_id: str):
        profile_ref = self.db.collection("profiles").document(uid)
        profile_snapshot = profile_ref.get()
        if not profile_snapshot.exists:
            raise HTTPException(status_code=404, detail="Profile not found")

        profile_data = profile_snapshot.to_dict()

        if profile_data.get("in_queue", True):
            raise HTTPException(status_code=400, detail="User already in queue")

        is_privileged = profile_data.get("is_privileged", False)

        queue_ref = self.db.collection("queues").document(queue_id)

        @firestore.transactional
        def transactional_update(transaction, queue_ref):
            snapshot = queue_ref.get(transaction=transaction)
            data = snapshot.to_dict() or {}
            next_ticket = data.get("next_ticket", 1)

            passenger_ref = queue_ref.collection("passengers").document(
                str(next_ticket)
            )

            transaction.set(
                passenger_ref,
                {
                    "user_id": uid,
                    "status": "waiting",
                    "ticket_number": next_ticket,
                    "is_privileged": is_privileged,
                    "joined_at": firestore.SERVER_TIMESTAMP,
                },
            )
            transaction.set(queue_ref, {"next_ticket": next_ticket + 1}, merge=True)
            return next_ticket

        transaction = self.db.transaction()
        ticket_number = transactional_update(transaction, queue_ref)
        profile_ref.set({"in_queue": True}, merge=True)
        return ticket_number

    def leave_queue(self, uid: str, queue_id: str):
        profile_ref = self.db.collection("profiles").document(uid)
        profile_snapshot = profile_ref.get()
        if not profile_snapshot.exists:
            raise HTTPException(status_code=404, detail="Profile not found")

        profile_data = profile_snapshot.to_dict() or {}
        if not profile_data.get("in_queue", False):
            raise HTTPException(status_code=400, detail="User is not in a queue")

        queue_ref = self.db.collection("queues").document(queue_id)

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
            transaction.delete(passenger_doc)

        transaction = self.db.transaction()
        transactional_update(transaction, queue_ref)

        profile_ref.set({"in_queue": False}, merge=True)

        return True

    def get_queue_status(self, uid: str, queue_id: str):
        queue_ref = self.db.collection("queues").document(queue_id)
        passengers_ref = queue_ref.collection("passengers")

        docs = list(passengers_ref.where("user_id", "==", uid).limit(1).stream())
        if not docs:
            raise HTTPException(status_code=404, detail="User not found in queue")

        my_doc = docs[0]
        my_data = my_doc.to_dict()
        # my_ticket = my_data["ticket_number"]
        # is_privileged = my_data.get("is_privileged", False)

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

        my_data["queue_number"] = queue_map[uid]

        return my_data

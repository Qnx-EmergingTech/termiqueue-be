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
            priority_seat = data.get("priority_seat", 5)
            # check how many seniors are in the first senior_seat(5) passengers, if less than senior_seat(5), allow the new senior passenger to take the first senior_seat(5) position

            passengers_ref = queue_ref.collection("passengers")
            passengers = passengers_ref.order_by("joined_at").stream(
                transaction=transaction
            )

            passengers_list = [p.to_dict() for p in passengers]

            if is_privileged:
                # count how many privileged already in front
                privileged_count = sum(
                    1 for p in passengers_list if p.get("is_privileged")
                )
                if privileged_count < priority_seat:
                    # place them just after the last privileged already seated
                    queue_number = privileged_count + 1
                else:
                    queue_number = len(passengers_list) + 1
            else:
                queue_number = len(passengers_list) + 1

            passenger_ref = passengers_ref.document(str(next_ticket))
            transaction.set(
                passenger_ref,
                {
                    "user_id": uid,
                    "status": "waiting",
                    "ticket_number": next_ticket,
                    "queue_number": queue_number,
                    "is_privileged": is_privileged,
                    "joined_at": firestore.SERVER_TIMESTAMP,
                },
            )
            transaction.set(queue_ref, {"next_ticket": next_ticket + 1}, merge=True)

            return queue_number

        transaction = self.db.transaction()
        queue_number = transactional_update(transaction, queue_ref)
        profile_ref.set({"in_queue": True}, merge=True)
        return {"queue_number": queue_number}

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

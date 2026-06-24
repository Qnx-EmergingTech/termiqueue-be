from typing import Dict, List
from fastapi import WebSocket
from loguru import logger


class WSManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, queue_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(queue_id, []).append(websocket)
        total = len(self.active_connections[queue_id])
        logger.info(
            f"WebSocket connected — queue_id={queue_id} active_connections={total}"
        )

    def disconnect(self, queue_id: str, websocket: WebSocket):
        if queue_id in self.active_connections:
            self.active_connections[queue_id].remove(websocket)
            if not self.active_connections[queue_id]:
                del self.active_connections[queue_id]
                logger.info(
                    f"WebSocket disconnected — queue_id={queue_id} no remaining connections"
                )
            else:
                total = len(self.active_connections[queue_id])
                logger.info(
                    f"WebSocket disconnected — queue_id={queue_id} active_connections={total}"
                )

    async def broadcast(self, queue_id: str, message: dict):
        dead = []
        event_type = message.get("type", "unknown")

        for ws in self.active_connections.get(queue_id, []):
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(
                    f"WebSocket broadcast failed — queue_id={queue_id} event={event_type} error={str(e)}"
                )
                dead.append(ws)

        for ws in dead:
            self.disconnect(queue_id, ws)

        if dead:
            logger.warning(
                f"Dead WebSocket connections removed — queue_id={queue_id} removed={len(dead)}"
            )
        else:
            total = len(self.active_connections.get(queue_id, []))
            logger.info(
                f"WebSocket broadcast — queue_id={queue_id} event={event_type} recipients={total}"
            )


ws_manager = WSManager()

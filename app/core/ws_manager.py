from typing import Dict, List
from fastapi import WebSocket
from loguru import logger
from prometheus_client import Counter, Gauge

ws_connections_total = Counter(
    "ws_connections_total",
    "Total WebSocket connections accepted",
    ["queue_id"],
)
ws_disconnections_total = Counter(
    "ws_disconnections_total",
    "Total WebSocket disconnections",
    ["queue_id"],
)
ws_active_connections = Gauge(
    "ws_active_connections",
    "Current number of active WebSocket connections",
    ["queue_id"],
)
ws_broadcast_total = Counter(
    "ws_broadcast_total",
    "Total WebSocket broadcast events sent",
    ["queue_id", "event_type"],
)
ws_broadcast_errors_total = Counter(
    "ws_broadcast_errors_total",
    "Total failed WebSocket sends (dead connection drops)",
    ["queue_id"],
)


class WSManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, queue_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(queue_id, []).append(websocket)
        ws_connections_total.labels(queue_id=queue_id).inc()
        ws_active_connections.labels(queue_id=queue_id).inc()
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
        ws_disconnections_total.labels(queue_id=queue_id).inc()
        ws_active_connections.labels(queue_id=queue_id).dec()

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
                ws_broadcast_errors_total.labels(queue_id=queue_id).inc()

        for ws in dead:
            self.disconnect(queue_id, ws)

        if dead:
            logger.warning(
                f"Dead WebSocket connections removed — queue_id={queue_id} removed={len(dead)}"
            )

        sent = len(self.active_connections.get(queue_id, []))
        logger.info(
            f"WebSocket broadcast — queue_id={queue_id} event={event_type} recipients={sent}"
        )
        ws_broadcast_total.labels(queue_id=queue_id, event_type=event_type).inc(sent)


ws_manager = WSManager()

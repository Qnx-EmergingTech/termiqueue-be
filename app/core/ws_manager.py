from typing import Dict, List
from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, queue_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(queue_id, []).append(websocket)

    def disconnect(self, queue_id: str, websocket: WebSocket):
        if queue_id in self.active_connections:
            self.active_connections[queue_id].remove(websocket)
            if not self.active_connections[queue_id]:
                del self.active_connections[queue_id]

    async def broadcast(self, queue_id: str, message: dict):
        dead = []
        for ws in self.active_connections.get(queue_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(queue_id, ws)


ws_manager = WSManager()

from fastapi import WebSocket, APIRouter, Depends, HTTPException
from starlette.websockets import WebSocketDisconnect
from typing import List
from security import get_current_user, get_user_from_token
from models import User

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[dict] = []

    async def connect(self, websocket: WebSocket, user: User, workspace_uuid: str):
        await websocket.accept()
        print("Appending", {"socket": websocket, "user": user, "workspace_uuid": workspace_uuid})
        self.active_connections.append({"socket": websocket, "user": user, "workspace_uuid": workspace_uuid})

    def disconnect(self, websocket: WebSocket):
        print("depending", websocket)
        self.active_connections = [conn for conn in self.active_connections if conn["socket"] != websocket]

    async def broadcast(self, message: dict, workspace_uuid: str):
        print("Doing Broadcast", self.active_connections)
        for conn in self.active_connections:
            print("Conn", conn, conn["workspace_uuid"], "Looking for", workspace_uuid)
            if conn["workspace_uuid"] == workspace_uuid:
                await conn["socket"].send_json(message)

manager = ConnectionManager()

@router.websocket("/ws/updates/{workspace_uuid}")
async def websocket_endpoint(websocket: WebSocket, workspace_uuid: str):
    token = websocket.query_params.get('token')
    if not token:
        await websocket.close(code=4001)
        return
    try:
        user_id = await get_user_from_token(token)
        await manager.connect(websocket, user_id, workspace_uuid)  # Properly use the connect method
        print(f"User {user_id} connected to workspace {workspace_uuid}")
        while True:
            data = await websocket.receive_text()
            # Process incoming messages, if any
    except WebSocketDisconnect:
        manager.disconnect(websocket)  # Ensure disconnection is also handled through the manager
        print(f"User {user_id} disconnected")
    except HTTPException as e:
        await websocket.send_text(str(e.detail))
        await websocket.close(code=e.status_code)
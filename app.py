from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict
import os

app = FastAPI()

# Data model for the poll request
class PollRequest(BaseModel):
    question: str
    options: List[str]

# Poll structure (store polls in memory)
polls: Dict[int, Dict[str, any]] = {}

# WebSocket manager to handle multiple connections
class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict):
        for connection in self.active_connections:
            await connection.send_json(message)

# Initialize WebSocket manager
manager = WebSocketManager()

@app.post("/create_poll")
async def create_poll(poll: PollRequest):
    if len(poll.options) < 2:
        raise HTTPException(status_code=400, detail="You must provide at least two options for the poll.")
    
    # Generate a unique poll ID (using UUID for better uniqueness)
    poll_id = len(polls) + 1
    polls[poll_id] = {"question": poll.question, "options": {option: 0 for option in poll.options}}
    
    return {"poll_id": poll_id, "question": poll.question, "options": polls[poll_id]["options"]}

@app.get("/poll/{poll_id}")
async def get_poll(poll_id: int):
    if poll_id not in polls:
        raise HTTPException(status_code=404, detail="Poll not found")
    
    return polls[poll_id]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            poll_id = data.get("poll_id")
            vote_option = data.get("vote")
            
            # Handle voting
            if poll_id and vote_option:
                poll = polls.get(poll_id)
                if poll and vote_option in poll["options"]:
                    poll["options"][vote_option] += 1
                    await manager.broadcast({"poll": poll})
                else:
                    await websocket.send_json({"error": "Invalid vote"})
            else:
                await websocket.send_json({"error": "Invalid poll data"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Serve static files (CSS, JS, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    # Path to your frontend HTML file
    html_file_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_file_path, "r") as file:
        html_content = file.read()
    return HTMLResponse(content=html_content)
@app.post("/reset_poll/{poll_id}")
async def reset_poll(poll_id: int):
    if poll_id not in polls:
        raise HTTPException(status_code=404, detail="Poll not found")
    for option in polls[poll_id]["options"]:
        polls[poll_id]["options"][option] = 0
    return {"message": "Poll reset successfully"}

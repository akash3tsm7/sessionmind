import os
import json
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import redis.asyncio as redis
import numpy as np

from products import PRODUCTS
from bandit import UCB1Bandit
from session import get_bandit, save_bandit, get_event_log, append_event

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = None
active_connections: dict[str, WebSocket] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    yield
    await redis_client.aclose()

app = FastAPI(title="SessionMind API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EventPayload(BaseModel):
    session_id: str
    product_id: str
    timestamp: str

@app.get("/api/products")
async def get_products():
    return {"products": PRODUCTS}

@app.get("/api/session/{session_id}/state")
async def get_session_state(session_id: str):
    bandit = await get_bandit(redis_client, session_id)
    event_log = await get_event_log(redis_client, session_id)
    total_clicks = int(np.sum(bandit.counts))
    top_indices = bandit.get_recommendations(total_clicks, 10)
    recommendations = [PRODUCTS[i] for i in top_indices]
    
    return {
        "session_id": session_id,
        "total_clicks": total_clicks,
        "event_log": event_log[-20:],
        "recommendations": recommendations,
        "category_boost": bandit.category_boost,
        "personalization_score": min(total_clicks * 8.5, 100.0)
    }

@app.post("/api/event")
async def handle_event(payload: EventPayload):
    # 1. Validate product_id
    try:
        arm_index = next(i for i, p in enumerate(PRODUCTS) if p["id"] == payload.product_id)
    except StopIteration:
        return {"error": "Invalid product_id"}
        
    # 3. Load bandit
    bandit = await get_bandit(redis_client, payload.session_id)
    
    # 4. Get category
    category = PRODUCTS[arm_index]["category"]
    
    # 5. Update bandit
    bandit.update(arm_index, [category])
    
    # 6. Save bandit
    await save_bandit(redis_client, payload.session_id, bandit)
    
    # 7. Build event dict
    event = {
        "product_id": payload.product_id,
        "product_name": PRODUCTS[arm_index]["name"],
        "category": category,
        "timestamp": payload.timestamp,
        "arm_index": arm_index
    }
    
    # 8. Append event
    await append_event(redis_client, payload.session_id, event)
    
    # 9. Get recommendations
    total_clicks = int(np.sum(bandit.counts))
    top_indices = bandit.get_recommendations(total_clicks, 10)
    recommendations = [PRODUCTS[i] for i in top_indices]
    
    # 10. Build push payload
    push_payload = {
        "type": "recommendation_update",
        "recommendations": recommendations,
        "category_boost": bandit.category_boost,
        "total_clicks": total_clicks,
        "personalization_score": min(total_clicks * 8.5, 100.0),
        "triggered_by": payload.product_id
    }
    
    # 11. Push via WebSocket
    if payload.session_id in active_connections:
        await active_connections[payload.session_id].send_json(push_payload)
        
    # 12. Return
    return {
        "status": "ok",
        "recommendations": recommendations,
        "total_clicks": total_clicks,
        "personalization_score": min(total_clicks * 8.5, 100.0)
    }

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    active_connections[session_id] = websocket
    
    try:
        # Send initial state
        bandit = await get_bandit(redis_client, session_id)
        total_clicks = int(np.sum(bandit.counts))
        top_indices = bandit.get_recommendations(total_clicks, 10)
        recommendations = [PRODUCTS[i] for i in top_indices]
        
        push_payload = {
            "type": "initial_state",
            "recommendations": recommendations,
            "category_boost": bandit.category_boost,
            "total_clicks": total_clicks,
            "personalization_score": min(total_clicks * 8.5, 100.0),
            "triggered_by": None
        }
        await websocket.send_json(push_payload)
        
        while True:
            # Wait for any messages from client (ignore them)
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        if session_id in active_connections:
            del active_connections[session_id]

@app.delete("/api/session/{session_id}")
async def reset_session(session_id: str):
    await redis_client.delete(f"session:{session_id}")
    await redis_client.delete(f"events:{session_id}")
    
    if session_id in active_connections:
        await active_connections[session_id].send_json({"type": "session_reset"})
        
    return {"status": "reset", "session_id": session_id}

@app.get("/api/health")
async def health_check():
    try:
        await redis_client.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "error"
    return {"status": "ok", "redis": redis_status}

# Must be mounted last
app.mount("/", StaticFiles(directory="static", html=True), name="static")

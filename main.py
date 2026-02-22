import hashlib
import os
from datetime import datetime, timezone
from typing import Any, Dict, Set, Tuple
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json

load_dotenv()
app = FastAPI(title="OpenAI Status Webhook Receiver", version="1.0.0")


def _normalize_token(token: str) -> str:
    return str(token or "").strip()


WEBHOOK_TOKEN = _normalize_token(os.getenv("WEBHOOK_TOKEN", "change-me"))
API_KEYWORDS = [
    "openai api",
    "chat completions",
    "responses",
    "embeddings",
    "assistants",
    "realtime",
]


seen_updates: Set[str] = set()
event_history: list = []
MAX_HISTORY = 50


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Handle cases where connection might have closed
                pass


manager = ConnectionManager()


def _token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def _to_text(value: Any) -> str:
    return str(value or "").strip()


def _is_api_related(name: str, incident_name: str, message: str) -> bool:
    haystack = f"{name} {incident_name} {message}".lower()
    return any(keyword in haystack for keyword in API_KEYWORDS)


def _extract_product_and_message(payload: Dict[str, Any]) -> Tuple[str, str]:
    incident = payload.get("incident", {}) or {}
    incident_name = _to_text(incident.get("name")) or "Unknown Incident"
    incident_status = _to_text(incident.get("status"))

    incident_update = payload.get("incident_update", {}) or {}
    body = _to_text(incident_update.get("body"))
    if not body:
        body = _to_text(incident.get("shortlink")) or "No message provided"

    components = incident.get("components", []) or []
    component_names = []
    for component in components:
        name = _to_text(component.get("name"))
        if name:
            component_names.append(name)

    if component_names:
        product = "OpenAI API - " + ", ".join(component_names)
    else:
        product = f"OpenAI API - {incident_name}"

    message = body
    if incident_status:
        message = f"{incident_status}: {body}"

    return product, message


def _build_dedupe_key(payload: Dict[str, Any], message: str) -> str:
    incident = payload.get("incident", {}) or {}
    incident_update = payload.get("incident_update", {}) or {}

    incident_id = _to_text(incident.get("id"))
    update_id = _to_text(incident_update.get("id"))
    updated_at = _to_text(incident_update.get("updated_at") or incident.get("updated_at"))

    if incident_id and update_id:
        return f"{incident_id}:{update_id}"

    fallback_raw = f"{incident_id}|{updated_at}|{message}"
    return hashlib.sha256(fallback_raw.encode("utf-8")).hexdigest()


def _extract_incident_name(payload: Dict[str, Any]) -> str:
    incident = payload.get("incident", {}) or {}
    return _to_text(incident.get("name"))


@app.get("/healthz")
async def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/webhooks/openai-status/{token}")
async def receive_openai_status_webhook(token: str, request: Request) -> Dict[str, Any]:
    incoming_token = _normalize_token(token)
    if incoming_token != WEBHOOK_TOKEN:
        print(
            "Webhook auth failed | "
            f"incoming_len={len(incoming_token)} incoming_fp={_token_fingerprint(incoming_token)} "
            f"expected_len={len(WEBHOOK_TOKEN)} expected_fp={_token_fingerprint(WEBHOOK_TOKEN)}"
        )
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

    product, message = _extract_product_and_message(payload)
    incident_name = _extract_incident_name(payload)

    if not _is_api_related(product, incident_name, message):
        return {"received": True, "printed": False, "reason": "non-api update"}

    dedupe_key = _build_dedupe_key(payload, message)
    if dedupe_key in seen_updates:
        return {"received": True, "printed": False, "reason": "duplicate update"}
    seen_updates.add(dedupe_key)

    event_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{event_ts}] OpenAI Update | Product: {product}")
    print(f"Status: {message}")

    # Track in history
    event_dict = {
        "timestamp": event_ts,
        "product": product,
        "status": message
    }
    event_history.insert(0, event_dict)
    if len(event_history) > MAX_HISTORY:
        event_history.pop()

    # Broadcast to websocket clients
    import asyncio
    asyncio.create_task(manager.broadcast(event_dict))

    return {"received": True, "printed": True, "dedupe_key": dedupe_key}


def _demo_payload() -> Dict[str, Any]:
    # Useful for quick local testing when no webhook is configured yet.
    return {
        "incident": {
            "id": "incident_123",
            "name": "Chat Completions Elevated Errors",
            "status": "investigating",
            "updated_at": "2026-02-22T12:00:00Z",
            "components": [{"name": "Chat Completions"}],
        },
        "incident_update": {
            "id": "update_001",
            "updated_at": "2026-02-22T12:01:00Z",
            "body": "Degraded performance due to upstream issue",
        },
    }


@app.post("/demo/trigger")
async def trigger_demo_event() -> Dict[str, Any]:
    payload = _demo_payload()
    product, message = _extract_product_and_message(payload)
    dedupe_key = _build_dedupe_key(payload, message)
    if dedupe_key not in seen_updates:
        seen_updates.add(dedupe_key)
        event_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{event_ts}] DEMO | Product: {product}")
        print(f"Status: {message}")
        
        event_dict = {
            "timestamp": event_ts,
            "product": product,
            "status": message
        }
        event_history.insert(0, event_dict)
        
        # Broadcast to websocket clients
        import asyncio
        asyncio.create_task(manager.broadcast(event_dict))
        
        return {"triggered": True, "printed": True}
    return {"triggered": True, "printed": False, "reason": "duplicate update"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    rows = ""
    for event in event_history:
        rows += f"""
        <div class="card">
            <div class="ts">{event['timestamp']}</div>
            <div class="product">{event['product']}</div>
            <div class="status">{event['status']}</div>
        </div>
        """
    
    if not rows:
        rows = "<p style='text-align:center; color:#666;'>No events yet...</p>"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>OpenAI Status Console (Real-time)</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f4f7f6; color: #333; margin: 0; padding: 20px; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            h1 {{ border-bottom: 2px solid #10a37f; padding-bottom: 10px; color: #10a37f; display: flex; align-items: center; justify-content: space-between; }}
            .status-dot {{ width: 10px; height: 10px; background: #bbb; border-radius: 50%; display: inline-block; margin-right: 10px; }}
            .status-dot.connected {{ background: #10a37f; }}
            .card {{ background: white; padding: 15px; margin-bottom: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #10a37f; animation: slideIn 0.3s ease-out; }}
            @keyframes slideIn {{ from {{ opacity: 0; transform: translateY(-10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
            .ts {{ font-size: 0.85em; color: #666; margin-bottom: 5px; }}
            .product {{ font-weight: bold; font-size: 1.1em; color: #111; }}
            .status {{ margin-top: 8px; line-height: 1.4; }}
            #history {{ margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>
                OpenAI Status Dashboard
                <span id="connection-status" class="status-dot" title="Disconnected"></span>
            </h1>
            <div id="history">
                {rows}
            </div>
        </div>

        <script>
            const historyDiv = document.getElementById('history');
            const statusDot = document.getElementById('connection-status');
            
            function connect() {{
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const ws = new WebSocket(`${{protocol}}//${{window.location.host}}/ws`);
                
                ws.onopen = () => {{
                    statusDot.classList.add('connected');
                    statusDot.title = 'Connected';
                    console.log('Connected to status stream');
                }};
                
                ws.onclose = () => {{
                    statusDot.classList.remove('connected');
                    statusDot.title = 'Disconnected (Attempting reconnect...)';
                    console.log('Disconnected. Reconnecting in 3s...');
                    setTimeout(connect, 3000);
                }};
                
                ws.onmessage = (event) => {{
                    const data = JSON.parse(event.data);
                    
                    // Remove "No events yet" message if it exists
                    if (historyDiv.innerText.includes('No events yet')) {{
                        historyDiv.innerHTML = '';
                    }}
                    
                    const newCard = document.createElement('div');
                    newCard.className = 'card';
                    newCard.innerHTML = `
                        <div class="ts">${{data.timestamp}}</div>
                        <div class="product">${{data.product}}</div>
                        <div class="status">${{data.status}}</div>
                    `;
                    
                    historyDiv.prepend(newCard);
                    
                    // Keep history to 50 items
                    if (historyDiv.children.length > 50) {{
                        historyDiv.removeChild(historyDiv.lastChild);
                    }}
                }};
            }}
            
            connect();
        </script>
    </body>
    </html>
    """
    return html_content


print(
    "Server config loaded | "
    f"WEBHOOK_TOKEN_len={len(WEBHOOK_TOKEN)} "
    f"WEBHOOK_TOKEN_fp={_token_fingerprint(WEBHOOK_TOKEN)} "
    f"is_default={WEBHOOK_TOKEN == 'change-me'}"
)

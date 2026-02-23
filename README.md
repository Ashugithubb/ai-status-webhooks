# OpenAI Status Webhook Receiver & Dashboard

A simple FastAPI application to receive OpenAI status updates via webhooks and display them on a real-time dashboard.

## Features
- **Real-time Dashboard**: Live updates using WebSockets (no refresh needed).
- **Public URL**: Clean interface to monitor API status.
- **Webhook Authentication**: Securely receive events using a token.
- **Demo Mode**: Trigger test events locally or via Postman.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Create a `.env` file in the root directory:
   ```env
   WEBHOOK_TOKEN=your_secret_token_here
   ```

## Running the App

Start the server using uvicorn:
```bash
python -m uvicorn main:app --reload
```

- **Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **Webhook URL**: `POST /webhooks/openai-status/{WEBHOOK_TOKEN}`

## Testing with Demo

You can trigger a demo event to test your dashboard:

**Option 1: Default Event**
```bash
curl -X POST http://localhost:8000/demo/trigger
```

**Option 2: Custom Event (Postman)**
- **URL**: `http://localhost:8000/demo/trigger`
- **Body**: raw (JSON)
- **Payload**:
  ```json
  {
      "incident": {
          "name": "Custom Outage",
          "status": "investigating"
      },
      "incident_update": {
          "body": "This is a custom test message!"
      }
  }
  ```

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

## Connecting OpenAI Status

To receive real-time updates from OpenAI, you need to expose your local server to the internet (using ngrok) OR Deploy it and configure a webhook on the OpenAI Status page.

### 1. Create a Tunnel (ngrok)
Since the app runs on `localhost`, OpenAI cannot send webhooks directly. Use [ngrok](https://ngrok.com/) or a similar tool to create a public tunnel:

```bash
ngrok http 8000
```
Copy the **Forwarding URL** (e.g., `https://random-id.ngrok-free.app`).

### 2. Configure OpenAI Webhook
1.  Go to [status.openai.com](https://status.openai.com/).
2.  Click on **Subscribe to Updates**.
3.  Select the **Webhook** tab (represented by a `< >` icon).
4.  Enter your Webhook URL:
    `https://your-tunnel-url.ngrok-free.app/webhooks/openai-status/your_secret_token_here`
    *(Replace `your_secret_token_here` with the value from your `.env` file)*.
5.  Click **Subscribe**.

### 3. Test the Connection
On the same OpenAI Status page, after adding the webhook, you can click **Test Webhook**. OpenAI will send a dummy payload to your server, which should appear on your dashboard instantly.

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

# main.py
from fastapi import Request
import uvicorn
from fastapi import FastAPI
from api_send import EvolutionAPI  # your sending class

# Create FastAPI app
app = FastAPI()

# Initialize the sending class
evo = EvolutionAPI()


@app.post("/")
async def webhook(request: Request):
    data = await request.json()
    print("📩 Received webhook:", data)

    # Optional: auto-reply
    # date_time = data.get("date_time")
    telephone = data["data"]["key"]["remoteJid"]
    # name = data["data"].get("pushName")
    # message_id = data["data"]["key"].get("id")
    message_text = data["data"]["message"].get("conversation")
    if telephone and message_text:
        reply_text = f"Received: {message_text}"
        evo.send_message(telephone, reply_text)
        print(f"📤 Sent reply to {telephone}")

    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9421, reload=True)

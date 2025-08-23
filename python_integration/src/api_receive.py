from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()


@app.post("/")
async def webhook(request: Request):
    data = await request.json()
    print("📩 Received webhook:", data)
    # you can process the message here
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9421, reload=True)

from fastapi import FastAPI
from app.profiles import router as profiles
from app.queues import router as queues

app = FastAPI()

app.include_router(profiles.router)
app.include_router(queues.router)


@app.get("/")
def read_root():
    return {"message": "API is running"}

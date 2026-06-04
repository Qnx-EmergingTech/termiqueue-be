from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.profiles import router as profiles
from app.queues import router as queues
from app.buses import router as buses
from app.geofence import router as geofence
from app.deploy import router as deploy

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router)
app.include_router(queues.router)
app.include_router(buses.router)
app.include_router(geofence.router)
app.include_router(deploy.router)


@app.get("/")
def read_root():
    return {"message": "API is running"}

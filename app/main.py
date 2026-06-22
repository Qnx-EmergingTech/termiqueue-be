from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from app.core.tracing_middleware import TracingMiddleware
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
app.add_middleware(TracingMiddleware)


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(profiles.router)
app.include_router(queues.router)
app.include_router(buses.router)
app.include_router(geofence.router)
app.include_router(deploy.router)


@app.get("/")
def read_root():
    return {"message": "API is running"}

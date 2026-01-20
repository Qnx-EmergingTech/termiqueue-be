from pydantic import BaseModel, Field, validator


class GeofenceConfig(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_meters: int = Field(..., gt=0, le=5000)

    @validator("radius_meters")
    def validate_radius(cls, v):
        if v <= 0:
            raise ValueError("Radius must be positive")
        return v

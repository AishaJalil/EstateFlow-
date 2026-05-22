from pydantic import BaseModel, Field


class MaintenanceCreate(BaseModel):
    property_id: str | None = None
    unit: str
    property_name: str
    original_issue: str
    latitude: float | None = None
    longitude: float | None = None


class MaintenanceApprove(BaseModel):
    approved: bool = True


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    property_id: str | None = None
    unit_id: str | None = None


class InspectionCreate(BaseModel):
    property_id: str | None = None
    property_name: str
    unit: str = "Common"
    inspection_type: str
    items: list[dict] = Field(default_factory=list)
    notes: dict = Field(default_factory=dict)


class PropertyCreate(BaseModel):
    name: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    total_units: int = 0
    latitude: float | None = None
    longitude: float | None = None
    unit_numbers: list[str] = Field(default_factory=list)


class UnitCreate(BaseModel):
    unit_number: str
    floor: int | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None


class VendorCreate(BaseModel):
    name: str
    specialty: str
    phone: str | None = None
    email: str | None = None
    password: str | None = Field(default=None, min_length=6)
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    area: str | None = None


class VendorRegister(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=6)
    specialty: str
    phone: str
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    area: str | None = None


class VendorLogin(BaseModel):
    email: str
    password: str

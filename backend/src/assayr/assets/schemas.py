import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from assayr.assets.models import Asset
from assayr.catalogue.schemas import OwnerOut

AssetType = Literal[
    "information",
    "application",
    "server",
    "endpoint",
    "network_device",
    "cloud_service",
    "facility",
    "people",
    "supplier_service",
]
Classification = Literal["public", "internal", "confidential", "restricted"]
Lifecycle = Literal["planned", "in_use", "retired"]
Rating = Annotated[int, Field(ge=1, le=5)]


class AssetIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: AssetType
    owner_id: uuid.UUID | None = None
    classification: Classification = "internal"
    confidentiality: Rating = 3
    integrity: Rating = 3
    availability: Rating = 3
    location: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=5000)
    lifecycle: Lifecycle = "in_use"


class AssetUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    type: AssetType | None = None
    owner_id: uuid.UUID | None = None
    classification: Classification | None = None
    confidentiality: Rating | None = None
    integrity: Rating | None = None
    availability: Rating | None = None
    location: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=5000)
    lifecycle: Lifecycle | None = None


class AssetOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    type: str
    owner: OwnerOut | None
    classification: str
    confidentiality: int
    integrity: int
    availability: int
    criticality: int
    location: str | None
    description: str | None
    lifecycle: str


def asset_out(asset: Asset) -> AssetOut:
    return AssetOut(
        id=asset.id,
        code=asset.code,
        name=asset.name,
        type=asset.type,
        owner=OwnerOut(id=asset.owner.id, full_name=asset.owner.full_name) if asset.owner else None,
        classification=asset.classification,
        confidentiality=asset.confidentiality,
        integrity=asset.integrity,
        availability=asset.availability,
        criticality=max(asset.confidentiality, asset.integrity, asset.availability),
        location=asset.location,
        description=asset.description,
        lifecycle=asset.lifecycle,
    )

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from assayr.assets.models import Asset
from assayr.catalogue.schemas import OwnerOut
from assayr.privacy.categories import level_label, unknown_categories

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
PiiVolume = Literal["lt100", "100_1k", "1k_10k", "gt10k"]
Categories = Annotated[list[str], Field(max_length=20)]


def _known(categories: list[str] | None) -> list[str] | None:
    bad = unknown_categories(categories or [])
    if bad:
        raise ValueError(f"Unknown personal-data categories: {', '.join(bad)}.")
    return categories


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
    holds_pii: bool = False
    pii_categories: Categories = []
    pii_sensitive: bool = False
    pii_volume: PiiVolume | None = None

    _categories = field_validator("pii_categories")(_known)


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
    holds_pii: bool | None = None
    pii_categories: Categories | None = None
    pii_sensitive: bool | None = None
    pii_volume: PiiVolume | None = None

    _categories = field_validator("pii_categories")(_known)


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
    confidentiality_label: str
    integrity_label: str
    availability_label: str
    criticality_label: str
    location: str | None
    description: str | None
    lifecycle: str
    holds_pii: bool
    pii_categories: list[str]
    pii_sensitive: bool
    pii_volume: str | None


def asset_out(asset: Asset) -> AssetOut:
    criticality = max(asset.confidentiality, asset.integrity, asset.availability)
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
        criticality=criticality,
        confidentiality_label=level_label(asset.confidentiality),
        integrity_label=level_label(asset.integrity),
        availability_label=level_label(asset.availability),
        criticality_label=level_label(criticality),
        location=asset.location,
        description=asset.description,
        lifecycle=asset.lifecycle,
        holds_pii=asset.holds_pii,
        pii_categories=list(asset.pii_categories or []),
        pii_sensitive=asset.pii_sensitive,
        pii_volume=asset.pii_volume,
    )

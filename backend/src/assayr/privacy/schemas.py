import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from assayr.catalogue.schemas import OwnerOut
from assayr.privacy.categories import unknown_categories
from assayr.privacy.models import DATA_SUBJECTS

LawfulBasis = Literal[
    "consent", "contract", "legal_obligation", "vital_interest", "public_interest", "legitimate_interest"
]
Status = Literal["draft", "active", "retired"]
Codes = Annotated[list[str], Field(max_length=20)]


def _categories(value: list[str] | None) -> list[str] | None:
    bad = unknown_categories(value or [])
    if bad:
        raise ValueError(f"Unknown personal-data categories: {', '.join(bad)}.")
    return value


def _subjects(value: list[str] | None) -> list[str] | None:
    bad = [s for s in value or [] if s not in DATA_SUBJECTS]
    if bad:
        raise ValueError(f"Unknown data subjects: {', '.join(bad)}.")
    return value


class ActivityIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    purpose: str | None = Field(None, max_length=5000)
    data_subjects: Codes = []
    data_categories: Codes = []
    lawful_basis: LawfulBasis
    recipients: str | None = Field(None, max_length=2000)
    cross_border: bool = False
    transfer_countries: str | None = Field(None, max_length=300)
    retention: str | None = Field(None, max_length=300)
    security_measures: str | None = Field(None, max_length=5000)
    owner_id: uuid.UUID | None = None
    status: Status = "draft"
    review_due: date | None = None

    _c = field_validator("data_categories")(_categories)
    _s = field_validator("data_subjects")(_subjects)


class ActivityUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    purpose: str | None = Field(None, max_length=5000)
    data_subjects: Codes | None = None
    data_categories: Codes | None = None
    lawful_basis: LawfulBasis | None = None
    recipients: str | None = Field(None, max_length=2000)
    cross_border: bool | None = None
    transfer_countries: str | None = Field(None, max_length=300)
    retention: str | None = Field(None, max_length=300)
    security_measures: str | None = Field(None, max_length=5000)
    owner_id: uuid.UUID | None = None
    status: Status | None = None
    review_due: date | None = None

    _c = field_validator("data_categories")(_categories)
    _s = field_validator("data_subjects")(_subjects)


class AssetLinksIn(BaseModel):
    asset_ids: list[uuid.UUID] = Field(max_length=500)


class LinkedAssetOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    criticality_label: str


class LinkedProcessorOut(BaseModel):
    id: uuid.UUID
    name: str
    dpa_signed: bool


class ActivityOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    purpose: str | None
    data_subjects: list[str]
    data_categories: list[str]
    lawful_basis: str
    recipients: str | None
    cross_border: bool
    transfer_countries: str | None
    retention: str | None
    security_measures: str | None
    owner: OwnerOut | None
    status: str
    review_due: date | None
    sensitive: bool
    review_overdue: bool
    assets: list[LinkedAssetOut]
    processors: list[LinkedProcessorOut] = []
    can_edit: bool


class ActivityRef(BaseModel):
    code: str
    name: str


class InventoryRow(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    type: str
    owner: OwnerOut | None
    pii_categories: list[str]
    pii_sensitive: bool
    pii_volume: str | None
    criticality: int
    criticality_label: str
    activities: list[ActivityRef]


class PrivacySummary(BaseModel):
    pii_assets: int
    sensitive_assets: int
    activities: int
    active_activities: int
    cross_border: int
    reviews_due: int
    requests_open: int = 0
    requests_overdue: int = 0
    breaches_open: int = 0
    notifications_overdue: int = 0

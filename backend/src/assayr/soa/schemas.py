from typing import Literal

from pydantic import BaseModel, Field

SourceKind = Literal["legal", "contractual", "business", "best_practice"]
MANUAL_SOURCES = {
    "legal": "Legal or regulatory",
    "contractual": "Contractual",
    "business": "Business requirement",
    "best_practice": "Best practice",
}


class SourceOut(BaseModel):
    kind: str
    label: str
    ref: str | None = None


class SoaItemOut(BaseModel):
    code: str
    title: str
    theme: str | None
    applicable: bool
    sources: list[SourceOut]
    justification: str | None
    exclusion_reason: str | None
    implementation_status: str
    status: str
    evidence_verified: int
    evidence_required: int
    owner: str | None


class ExcludedMitigatingOut(BaseModel):
    code: str
    risks: list[str]


class SoaChecksOut(BaseModel):
    orphans: list[str]
    excluded_mitigating: list[ExcludedMitigatingOut]
    untreated_risks: list[str]
    ok: bool


class SoaOut(BaseModel):
    items: list[SoaItemOut]
    checks: SoaChecksOut


class SoaItemsIn(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=200)
    applicable: bool | None = None
    sources: list[SourceKind] | None = Field(None, max_length=4)
    justification: str | None = Field(None, max_length=5000)
    exclusion_reason: str | None = Field(None, max_length=2000)

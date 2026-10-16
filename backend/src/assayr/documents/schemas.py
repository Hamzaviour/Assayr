import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from assayr.catalogue.schemas import OwnerOut
from assayr.documents.models import Document
from assayr.identity.models import User

DocType = Literal["policy", "procedure", "guideline"]
Code = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9][A-Za-z0-9._\-]*$")


class DocumentIn(BaseModel):
    doc_type: DocType
    code: str = Code
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    owner_id: uuid.UUID | None = None


class DocumentUpdateIn(BaseModel):
    doc_type: DocType | None = None
    code: str | None = Field(None, min_length=1, max_length=30, pattern=r"^[A-Za-z0-9][A-Za-z0-9._\-]*$")
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    owner_id: uuid.UUID | None = None
    review_due: date | None = None
    status: Literal["retired"] | None = None


class ControlLinksIn(BaseModel):
    codes: list[str] = Field(max_length=200)


class ControlDocumentOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    status: str
    version_label: str
    review_due: date | None
    review_overdue: bool = False
    approved_version: str | None


class ControlDocumentsOut(BaseModel):
    policy: list[ControlDocumentOut]
    procedure: list[ControlDocumentOut]
    guideline: list[ControlDocumentOut]


class LinkedControlOut(BaseModel):
    code: str
    title: str
    status: str


class HistoryOut(BaseModel):
    at: datetime
    actor: str | None
    action: str


class DocumentOut(BaseModel):
    id: uuid.UUID
    doc_type: str
    code: str
    title: str
    description: str | None
    owner: OwnerOut | None
    status: str
    version_label: str
    approved_by: OwnerOut | None
    approved_at: datetime | None
    review_due: date | None
    review_overdue: bool
    filename: str | None
    size: int | None
    approved_version: str | None
    approved_filename: str | None
    can_edit: bool
    can_approve: bool


class DocumentDetailOut(DocumentOut):
    controls: list[LinkedControlOut]
    history: list[HistoryOut]


def _person(user: User | None) -> OwnerOut | None:
    return OwnerOut(id=user.id, full_name=user.full_name) if user else None


def document_out(doc: Document, today: date, can_edit: bool, can_approve: bool) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        doc_type=doc.doc_type,
        code=doc.code,
        title=doc.title,
        description=doc.description,
        owner=_person(doc.owner),
        status=doc.status,
        version_label=doc.version_label,
        approved_by=_person(doc.approved_by),
        approved_at=doc.approved_at,
        review_due=doc.review_due,
        review_overdue=doc.status == "approved" and doc.review_due is not None and doc.review_due < today,
        filename=doc.filename,
        size=doc.size,
        approved_version=doc.approved_version,
        approved_filename=doc.approved_filename,
        can_edit=can_edit,
        can_approve=can_approve,
    )

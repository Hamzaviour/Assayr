"""Training courses for ISMS managers: materials, the assessment, publishing."""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.router import resolve_scope
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.storage import TooLargeError, safe_filename
from assayr.training.drive import MP4, PDF, WEBM, drive_file_id, preview_url, training_mime
from assayr.training.models import Assessment, Assignment, Course, CourseMaterial, Question, QuestionOption
from assayr.training.schemas import (
    AssessmentIn,
    AssessmentOut,
    CourseDetailOut,
    CourseIn,
    CourseOut,
    CourseUpdateIn,
    DriveMaterialIn,
    MaterialOut,
    MaterialUpdateIn,
)
from assayr.training.service import counts, course_assignments

router = APIRouter(tags=["training"])
NOT_FOUND = "Course not found."
HEAD_BYTES = 64
INLINE = (MP4, WEBM, PDF)


def material_out(m: CourseMaterial) -> MaterialOut:
    return MaterialOut(
        id=m.id,
        sort_order=m.sort_order,
        kind=m.kind,
        title=m.title,
        drive_file_id=m.drive_file_id,
        preview_url=preview_url(m.drive_file_id) if m.drive_file_id else None,
        filename=m.filename,
        mime=m.mime,
        size=m.size,
    )


def _course_out(db: Session, request: Request, course: Course) -> CourseOut:
    questions = len(course.assessment.questions) if course.assessment else 0
    return CourseOut(
        id=course.id,
        title=course.title,
        description=course.description,
        status=course.status,
        recurrence_months=course.recurrence_months,
        due_days=course.due_days,
        created_at=course.created_at,
        material_count=len(course.materials),
        question_count=questions,
        counts=counts(course_assignments(db, course), get_clock(request)().date()),
    )


def _detail(db: Session, request: Request, course: Course) -> CourseDetailOut:
    return CourseDetailOut(
        **_course_out(db, request, course).model_dump(),
        materials=[material_out(m) for m in course.materials],
        assessment=AssessmentOut.model_validate(course.assessment) if course.assessment else None,
        rules=sorted(r.target for r in course.rules),
        has_assignments=_has_assignments(db, course),
    )


def _has_assignments(db: Session, course: Course) -> bool:
    return db.scalar(select(Assignment.id).where(Assignment.course_id == course.id).limit(1)) is not None


def get_course(db: Session, grant: Grant, course_id: uuid.UUID) -> Course:
    course = db.get(Course, course_id)
    if course is None or not grant.allows(course.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return course


def _material(course: Course, material_id: uuid.UUID) -> CourseMaterial:
    found = next((m for m in course.materials if m.id == material_id), None)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found.")
    return found


def _locked(db: Session, course: Course, what: str) -> None:
    if _has_assignments(db, course):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"People are already taking this course, so its {what} can't change. Archive it and create a new course.",
        )


def material_file_response(request: Request, material: CourseMaterial) -> FileResponse:
    if material.sha256 is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This material has no file.")
    path = request.app.state.store.path_for(material.sha256)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The stored file is missing. Ask an administrator.")
    inline = material.mime in INLINE
    return FileResponse(
        path,
        filename=material.filename or "material",
        media_type=material.mime if inline else "application/octet-stream",
        content_disposition_type="inline" if inline else "attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/courses", response_model=list[CourseOut])
def list_courses(
    request: Request,
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[CourseOut]:
    scope = resolve_scope(db, scope_id, grant)
    courses = db.scalars(select(Course).where(Course.scope_id == scope.id).order_by(Course.created_at.desc()))
    return [_course_out(db, request, c) for c in courses.unique()]


@router.post("/courses", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(
    body: CourseIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> CourseOut:
    scope = resolve_scope(db, scope_id, grant)
    course = Course(scope_id=scope.id, created_by_id=user.id, **body.model_dump())
    db.add(course)
    db.flush()
    record(
        db, actor_for(request, user), "course.create", "course", str(course.id), diff={"title": course.title}
    )
    db.commit()
    db.refresh(course)
    return _course_out(db, request, course)


@router.get("/courses/{course_id}", response_model=CourseDetailOut)
def get_course_detail(
    course_id: uuid.UUID,
    request: Request,
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
) -> CourseDetailOut:
    return _detail(db, request, get_course(db, grant, course_id))


@router.patch("/courses/{course_id}", response_model=CourseDetailOut)
def update_course(
    course_id: uuid.UUID,
    body: CourseUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
) -> CourseDetailOut:
    course = get_course(db, grant, course_id)
    fields = body.model_fields_set
    if "title" in fields and body.title is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The title can not be empty.")
    if "due_days" in fields and body.due_days is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Set how many days people have to finish.")
    diff = {}
    for name in ("title", "description", "recurrence_months", "due_days"):
        if name in fields and getattr(body, name) != getattr(course, name):
            diff[name] = [getattr(course, name), getattr(body, name)]
            setattr(course, name, getattr(body, name))
    if diff:
        record(db, actor_for(request, user), "course.update", "course", str(course.id), diff=diff)
        db.commit()
    return _detail(db, request, course)


@router.post("/courses/{course_id}/materials/drive", response_model=MaterialOut, status_code=201)
def add_drive_material(
    course_id: uuid.UUID,
    body: DriveMaterialIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
) -> MaterialOut:
    course = get_course(db, grant, course_id)
    try:
        file_id = drive_file_id(body.url)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    material = CourseMaterial(
        sort_order=len(course.materials) + 1, kind="drive", title=body.title.strip(), drive_file_id=file_id
    )
    course.materials.append(material)
    db.flush()
    record(
        db,
        actor_for(request, user),
        "course.material",
        "course",
        str(course.id),
        diff={"added": material.title},
    )
    db.commit()
    return material_out(material)


@router.post("/courses/{course_id}/materials/file", response_model=MaterialOut, status_code=201)
def add_file_material(
    course_id: uuid.UUID,
    request: Request,
    title: str = Form(..., min_length=1, max_length=200),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
) -> MaterialOut:
    course = get_course(db, grant, course_id)
    filename = safe_filename(file.filename or "")
    mime = training_mime(file.file.read(HEAD_BYTES), filename)
    file.file.seek(0)
    if mime is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Upload a video (MP4, WebM), a PDF, or a Word or PowerPoint file.",
        )
    limit = request.app.state.settings.training_upload_mb
    try:
        blob = request.app.state.store.put(file.file, limit * 1024 * 1024)
    except TooLargeError as exc:
        raise HTTPException(413, f"The file is larger than the {limit} MB limit for training files.") from exc
    material = CourseMaterial(
        sort_order=len(course.materials) + 1,
        kind="file",
        title=title.strip(),
        sha256=blob.sha256,
        filename=filename,
        mime=mime,
        size=blob.size,
    )
    course.materials.append(material)
    db.flush()
    record(
        db,
        actor_for(request, user),
        "course.material",
        "course",
        str(course.id),
        diff={"added": material.title, "filename": filename, "sha256": blob.sha256},
    )
    db.commit()
    return material_out(material)


@router.patch("/courses/{course_id}/materials/{material_id}", response_model=CourseDetailOut)
def update_material(
    course_id: uuid.UUID,
    material_id: uuid.UUID,
    body: MaterialUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
) -> CourseDetailOut:
    course = get_course(db, grant, course_id)
    material = _material(course, material_id)
    if body.title is not None:
        material.title = body.title.strip()
    if body.sort_order is not None:
        ordered = [m for m in course.materials if m.id != material.id]
        ordered.insert(min(body.sort_order, len(ordered)), material)
        for index, m in enumerate(ordered, start=1):
            m.sort_order = index
    record(
        db,
        actor_for(request, user),
        "course.material",
        "course",
        str(course.id),
        diff={"updated": material.title},
    )
    db.commit()
    db.refresh(course)
    return _detail(db, request, course)


@router.delete("/courses/{course_id}/materials/{material_id}", response_model=CourseDetailOut)
def delete_material(
    course_id: uuid.UUID,
    material_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
) -> CourseDetailOut:
    course = get_course(db, grant, course_id)
    material = _material(course, material_id)
    _locked(db, course, "materials")
    course.materials.remove(material)
    for index, m in enumerate(course.materials, start=1):
        m.sort_order = index
    record(
        db,
        actor_for(request, user),
        "course.material",
        "course",
        str(course.id),
        diff={"removed": material.title},
    )
    db.commit()
    db.refresh(course)
    return _detail(db, request, course)


@router.get("/courses/{course_id}/materials/{material_id}/file")
def download_material(
    course_id: uuid.UUID,
    material_id: uuid.UUID,
    request: Request,
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
) -> FileResponse:
    return material_file_response(request, _material(get_course(db, grant, course_id), material_id))


@router.put("/courses/{course_id}/assessment", response_model=AssessmentOut | None)
def set_assessment(
    course_id: uuid.UUID,
    body: AssessmentIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
) -> AssessmentOut | None:
    """Replaces the whole assessment; an empty question list removes it."""
    course = get_course(db, grant, course_id)
    _locked(db, course, "assessment")
    if course.assessment is not None:
        db.delete(course.assessment)
        db.flush()
        db.refresh(course)
    if body.questions:
        course.assessment = Assessment(
            pass_mark=body.pass_mark,
            max_attempts=body.max_attempts,
            shuffle=body.shuffle,
            questions=[
                Question(
                    sort_order=qi,
                    kind=q.kind,
                    text=q.text.strip(),
                    options=[
                        QuestionOption(sort_order=oi, text=o.text.strip(), is_correct=o.is_correct)
                        for oi, o in enumerate(q.options, start=1)
                    ],
                )
                for qi, q in enumerate(body.questions, start=1)
            ],
        )
    record(
        db,
        actor_for(request, user),
        "course.assessment",
        "course",
        str(course.id),
        diff={
            "questions": len(body.questions),
            "pass_mark": body.pass_mark,
            "max_attempts": body.max_attempts,
        },
    )
    db.commit()
    db.refresh(course)
    return AssessmentOut.model_validate(course.assessment) if course.assessment else None


def _set_status(db: Session, request: Request, user: User, course: Course, new: str) -> None:
    record(
        db,
        actor_for(request, user),
        f"course.{new}",
        "course",
        str(course.id),
        diff={"status": [course.status, new]},
    )
    course.status = new
    db.commit()


@router.post("/courses/{course_id}/publish", response_model=CourseDetailOut)
def publish_course(
    course_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
) -> CourseDetailOut:
    course = get_course(db, grant, course_id)
    if not course.materials:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add at least one video or document before publishing.")
    _set_status(db, request, user, course, "published")
    return _detail(db, request, course)


@router.post("/courses/{course_id}/archive", response_model=CourseDetailOut)
def archive_course(
    course_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.TRAINING_MANAGE)),
    db: Session = Depends(get_session),
) -> CourseDetailOut:
    course = get_course(db, grant, course_id)
    _set_status(db, request, user, course, "archived")
    return _detail(db, request, course)

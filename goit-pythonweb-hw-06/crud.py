from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Grade, Group, Student, Subject, Teacher

MODELS = {
    "group": Group,
    "student": Student,
    "teacher": Teacher,
    "subject": Subject,
    "grade": Grade,
}

CreateBuilder = Callable[[Any], Any]
UpdateHandler = Callable[[Any, Any], None]
Serializer = Callable[[Any], dict[str, Any]]


def normalize_model_name(model_name: str) -> str:
    normalized = model_name.strip().lower()
    if normalized.endswith("s"):
        normalized = normalized[:-1]
    return normalized


def get_model(model_name: str):
    normalized = normalize_model_name(model_name)
    if normalized not in MODELS:
        raise ValueError(f"Unknown model: {model_name}")
    return MODELS[normalized]


def _parse_date(date_value: str | None):
    if not date_value:
        return None
    try:
        return datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Date must be in format YYYY-MM-DD") from exc


def _option_name(field: str) -> str:
    return f"--{field.replace('_', '-')}"


def _require_fields(args: Any, *fields: str) -> None:
    missing = [field for field in fields if getattr(args, field, None) is None]
    if missing:
        joined = " ".join(_option_name(field) for field in missing)
        raise ValueError(f"Missing required arguments: {joined}")


def _build_group(args: Any) -> Group:
    _require_fields(args, "name")
    return Group(name=args.name)


def _build_teacher(args: Any) -> Teacher:
    _require_fields(args, "name")
    return Teacher(full_name=args.name)


def _build_student(args: Any) -> Student:
    _require_fields(args, "name", "group_id")
    return Student(full_name=args.name, group_id=args.group_id)


def _build_subject(args: Any) -> Subject:
    _require_fields(args, "name", "teacher_id")
    return Subject(name=args.name, teacher_id=args.teacher_id)


def _build_grade(args: Any) -> Grade:
    _require_fields(args, "student_id", "subject_id", "grade")
    parsed_date = _parse_date(args.date)
    payload = {
        "student_id": args.student_id,
        "subject_id": args.subject_id,
        "grade": args.grade,
    }
    if parsed_date is not None:
        payload["date_received"] = parsed_date
    return Grade(**payload)


CREATE_BUILDERS: dict[type, CreateBuilder] = {
    Group: _build_group,
    Teacher: _build_teacher,
    Student: _build_student,
    Subject: _build_subject,
    Grade: _build_grade,
}


def _update_group(entity: Group, args: Any) -> None:
    if args.name:
        entity.name = args.name


def _update_teacher(entity: Teacher, args: Any) -> None:
    if args.name:
        entity.full_name = args.name


def _update_student(entity: Student, args: Any) -> None:
    if args.name:
        entity.full_name = args.name
    if args.group_id is not None:
        entity.group_id = args.group_id


def _update_subject(entity: Subject, args: Any) -> None:
    if args.name:
        entity.name = args.name
    if args.teacher_id is not None:
        entity.teacher_id = args.teacher_id


def _update_grade(entity: Grade, args: Any) -> None:
    if args.student_id is not None:
        entity.student_id = args.student_id
    if args.subject_id is not None:
        entity.subject_id = args.subject_id
    if args.grade is not None:
        entity.grade = args.grade
    if args.date is not None:
        parsed_date = _parse_date(args.date)
        if parsed_date is not None:
            entity.date_received = parsed_date


UPDATE_HANDLERS: dict[type, UpdateHandler] = {
    Group: _update_group,
    Teacher: _update_teacher,
    Student: _update_student,
    Subject: _update_subject,
    Grade: _update_grade,
}


SERIALIZERS: dict[type, Serializer] = {
    Group: lambda entity: {"id": entity.id, "name": entity.name},
    Teacher: lambda entity: {"id": entity.id, "full_name": entity.full_name},
    Student: lambda entity: {
        "id": entity.id,
        "full_name": entity.full_name,
        "group_id": entity.group_id,
    },
    Subject: lambda entity: {
        "id": entity.id,
        "name": entity.name,
        "teacher_id": entity.teacher_id,
    },
    Grade: lambda entity: {
        "id": entity.id,
        "student_id": entity.student_id,
        "subject_id": entity.subject_id,
        "grade": entity.grade,
        "date_received": entity.date_received.isoformat(),
    },
}


def create_entity(session: Session, model_name: str, args: Any) -> Any:
    model = get_model(model_name)

    builder = CREATE_BUILDERS.get(model)
    if builder is None:
        raise ValueError(f"Create is not configured for model: {model.__name__}")
    entity = builder(args)

    session.add(entity)
    session.flush()
    return entity


def list_entities(session: Session, model_name: str) -> list[Any]:
    model = get_model(model_name)
    stmt = select(model).order_by(model.id)
    return list(session.execute(stmt).scalars().all())


def update_entity(session: Session, model_name: str, args: Any) -> Any:
    if args.id is None:
        raise ValueError("Update requires --id")

    model = get_model(model_name)
    entity = session.get(model, args.id)
    if not entity:
        raise ValueError(f"{model.__name__} with id={args.id} not found")

    handler = UPDATE_HANDLERS.get(model)
    if handler is None:
        raise ValueError(f"Update is not configured for model: {model.__name__}")
    handler(entity, args)

    session.flush()
    return entity


def remove_entity(session: Session, model_name: str, args: Any) -> int:
    if args.id is None:
        raise ValueError("Remove requires --id")

    model = get_model(model_name)
    entity = session.get(model, args.id)
    if not entity:
        raise ValueError(f"{model.__name__} with id={args.id} not found")

    session.delete(entity)
    session.flush()
    return args.id


def entity_to_dict(entity: Any) -> dict[str, Any]:
    serializer = SERIALIZERS.get(type(entity))
    if serializer is not None:
        return serializer(entity)
    return {"value": str(entity)}

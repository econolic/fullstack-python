from __future__ import annotations

from typing import Any

from sqlalchemy import desc, distinct, func, select
from sqlalchemy.orm import Session

from models import Grade, Group, Student, Subject


def select_1(session: Session, limit: int = 5) -> list[dict[str, Any]]:
    stmt = (
        select(
            Student.id.label("student_id"),
            Student.full_name.label("student_name"),
            func.round(func.avg(Grade.grade), 2).label("average_grade"),
        )
        .join(Grade, Grade.student_id == Student.id)
        .group_by(Student.id, Student.full_name)
        .order_by(desc("average_grade"))
        .limit(limit)
    )
    return [dict(row) for row in session.execute(stmt).mappings().all()]


def select_2(session: Session, subject_id: int) -> dict[str, Any] | None:
    stmt = (
        select(
            Student.id.label("student_id"),
            Student.full_name.label("student_name"),
            Subject.id.label("subject_id"),
            Subject.name.label("subject_name"),
            func.round(func.avg(Grade.grade), 2).label("average_grade"),
        )
        .join(Grade, Grade.student_id == Student.id)
        .join(Subject, Subject.id == Grade.subject_id)
        .where(Subject.id == subject_id)
        .group_by(Student.id, Student.full_name, Subject.id, Subject.name)
        .order_by(desc("average_grade"))
        .limit(1)
    )
    row = session.execute(stmt).mappings().first()
    return dict(row) if row else None


def select_3(session: Session, subject_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(
            Group.id.label("group_id"),
            Group.name.label("group_name"),
            Subject.id.label("subject_id"),
            Subject.name.label("subject_name"),
            func.round(func.avg(Grade.grade), 2).label("average_grade"),
        )
        .join(Student, Student.group_id == Group.id)
        .join(Grade, Grade.student_id == Student.id)
        .join(Subject, Subject.id == Grade.subject_id)
        .where(Subject.id == subject_id)
        .group_by(Group.id, Group.name, Subject.id, Subject.name)
        .order_by(Group.name)
    )
    return [dict(row) for row in session.execute(stmt).mappings().all()]


def select_4(session: Session) -> dict[str, Any]:
    stmt = select(func.round(func.avg(Grade.grade), 2).label("average_grade"))
    value = session.execute(stmt).scalar_one_or_none()
    return {"average_grade": value}


def select_5(session: Session, teacher_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(Subject.id.label("subject_id"), Subject.name.label("subject_name"))
        .where(Subject.teacher_id == teacher_id)
        .order_by(Subject.name)
    )
    return [dict(row) for row in session.execute(stmt).mappings().all()]


def select_6(session: Session, group_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(Student.id.label("student_id"), Student.full_name.label("student_name"))
        .where(Student.group_id == group_id)
        .order_by(Student.full_name)
    )
    return [dict(row) for row in session.execute(stmt).mappings().all()]


def select_7(session: Session, group_id: int, subject_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(
            Student.id.label("student_id"),
            Student.full_name.label("student_name"),
            Subject.id.label("subject_id"),
            Subject.name.label("subject_name"),
            Grade.grade.label("grade"),
            Grade.date_received.label("date_received"),
        )
        .join(Grade, Grade.student_id == Student.id)
        .join(Subject, Subject.id == Grade.subject_id)
        .where(Student.group_id == group_id, Subject.id == subject_id)
        .order_by(Student.full_name, Grade.date_received)
    )
    return [dict(row) for row in session.execute(stmt).mappings().all()]


def select_8(session: Session, teacher_id: int) -> dict[str, Any]:
    stmt = (
        select(func.round(func.avg(Grade.grade), 2).label("average_grade"))
        .join(Subject, Subject.id == Grade.subject_id)
        .where(Subject.teacher_id == teacher_id)
    )
    value = session.execute(stmt).scalar_one_or_none()
    return {"teacher_id": teacher_id, "average_grade": value}


def select_9(session: Session, student_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(
            distinct(Subject.id).label("subject_id"), Subject.name.label("subject_name")
        )
        .join(Grade, Grade.subject_id == Subject.id)
        .where(Grade.student_id == student_id)
        .order_by(Subject.name)
    )
    return [dict(row) for row in session.execute(stmt).mappings().all()]


def select_10(
    session: Session, student_id: int, teacher_id: int
) -> list[dict[str, Any]]:
    stmt = (
        select(
            distinct(Subject.id).label("subject_id"), Subject.name.label("subject_name")
        )
        .join(Grade, Grade.subject_id == Subject.id)
        .where(Grade.student_id == student_id, Subject.teacher_id == teacher_id)
        .order_by(Subject.name)
    )
    return [dict(row) for row in session.execute(stmt).mappings().all()]


def advanced_select_1(
    session: Session, teacher_id: int, student_id: int
) -> dict[str, Any]:
    stmt = (
        select(func.round(func.avg(Grade.grade), 2).label("average_grade"))
        .join(Subject, Subject.id == Grade.subject_id)
        .where(Subject.teacher_id == teacher_id, Grade.student_id == student_id)
    )
    value = session.execute(stmt).scalar_one_or_none()
    return {"teacher_id": teacher_id, "student_id": student_id, "average_grade": value}


def advanced_select_2(
    session: Session, group_id: int, subject_id: int
) -> list[dict[str, Any]]:
    latest_date_sq = (
        select(func.max(Grade.date_received))
        .join(Student, Student.id == Grade.student_id)
        .where(Student.group_id == group_id, Grade.subject_id == subject_id)
        .scalar_subquery()
    )

    stmt = (
        select(
            Student.id.label("student_id"),
            Student.full_name.label("student_name"),
            Grade.grade.label("grade"),
            Grade.date_received.label("date_received"),
        )
        .join(Grade, Grade.student_id == Student.id)
        .where(
            Student.group_id == group_id,
            Grade.subject_id == subject_id,
            Grade.date_received == latest_date_sq,
        )
        .order_by(Student.full_name)
    )
    return [dict(row) for row in session.execute(stmt).mappings().all()]

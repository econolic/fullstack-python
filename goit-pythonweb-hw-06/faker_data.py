from __future__ import annotations

import random
from datetime import date

from faker import Faker
from sqlalchemy import delete
from sqlalchemy.orm import Session

from models import Grade, Group, Student, Subject, Teacher


def _build_subject_titles() -> list[str]:
    return [
        "Mathematics",
        "Physics",
        "Chemistry",
        "Biology",
        "History",
        "Geography",
        "Literature",
        "Programming",
        "Databases",
        "Algorithms",
    ]


def populate_database(
    session: Session, reset: bool = False, seed: int | None = None
) -> dict[str, int]:
    faker = Faker("uk_UA")

    if seed is not None:
        random.seed(seed)
        faker.seed_instance(seed)

    if reset:
        session.execute(delete(Grade))
        session.execute(delete(Student))
        session.execute(delete(Subject))
        session.execute(delete(Teacher))
        session.execute(delete(Group))
        session.flush()

    groups = [Group(name=name) for name in ("AD-101", "BD-202", "CD-303")]
    session.add_all(groups)
    session.flush()

    teachers_count = random.randint(3, 5)
    teachers = [Teacher(full_name=faker.name()) for _ in range(teachers_count)]
    session.add_all(teachers)
    session.flush()

    subject_count = random.randint(5, 8)
    all_subjects = _build_subject_titles()
    random.shuffle(all_subjects)
    selected_subjects = all_subjects[:subject_count]

    subjects = [
        Subject(name=subject_name, teacher=random.choice(teachers))
        for subject_name in selected_subjects
    ]
    session.add_all(subjects)
    session.flush()

    students_count = random.randint(30, 50)
    students = [
        Student(full_name=faker.name(), group=random.choice(groups))
        for _ in range(students_count)
    ]
    session.add_all(students)
    session.flush()

    grades: list[Grade] = []
    for student in students:
        for _ in range(random.randint(10, 20)):
            grades.append(
                Grade(
                    student=student,
                    subject=random.choice(subjects),
                    grade=random.randint(1, 12),
                    date_received=faker.date_between(
                        start_date="-180d", end_date=date.today()
                    ),
                )
            )

    session.add_all(grades)
    session.flush()

    return {
        "groups": len(groups),
        "teachers": len(teachers),
        "subjects": len(subjects),
        "students": len(students),
        "grades": len(grades),
    }

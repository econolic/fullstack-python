from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    validates,
)


class Base(DeclarativeBase):
    pass


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)

    students: Mapped[list[Student]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )

    @validates("name")
    def validate_name(self, _: str, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Group name cannot be empty")
        return cleaned

    def __repr__(self) -> str:
        return f"Group(id={self.id}, name='{self.name}')"


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="RESTRICT"), nullable=False
    )

    group: Mapped[Group] = relationship(back_populates="students")
    grades: Mapped[list[Grade]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )

    @validates("full_name")
    def validate_full_name(self, _: str, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Student name cannot be empty")
        return cleaned

    def __repr__(self) -> str:
        return f"Student(id={self.id}, full_name='{self.full_name}', group_id={self.group_id})"


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)

    subjects: Mapped[list[Subject]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )

    @validates("full_name")
    def validate_full_name(self, _: str, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Teacher name cannot be empty")
        return cleaned

    def __repr__(self) -> str:
        return f"Teacher(id={self.id}, full_name='{self.full_name}')"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False
    )

    teacher: Mapped[Teacher] = relationship(back_populates="subjects")
    grades: Mapped[list[Grade]] = relationship(
        back_populates="subject", cascade="all, delete-orphan"
    )

    @validates("name")
    def validate_name(self, _: str, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Subject name cannot be empty")
        return cleaned

    def __repr__(self) -> str:
        return (
            f"Subject(id={self.id}, name='{self.name}', teacher_id={self.teacher_id})"
        )


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (
        CheckConstraint("grade >= 1 AND grade <= 12", name="check_grade_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    date_received: Mapped[date] = mapped_column(
        Date, default=date.today, nullable=False
    )

    student: Mapped[Student] = relationship(back_populates="grades")
    subject: Mapped[Subject] = relationship(back_populates="grades")

    @validates("grade")
    def validate_grade(self, _: str, value: int) -> int:
        if not 1 <= value <= 12:
            raise ValueError("Grade must be between 1 and 12")
        return value

    def __repr__(self) -> str:
        return (
            f"Grade(id={self.id}, student_id={self.student_id}, subject_id={self.subject_id}, "
            f"grade={self.grade}, date_received={self.date_received})"
        )

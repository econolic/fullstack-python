from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Any, Callable

SelectRunner = Callable[[Any, argparse.Namespace], Any]
LOGGER = logging.getLogger("hw06.cli")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _option_name(field: str) -> str:
    return f"--{field.replace('_', '-')}"


def _validate_required_query_args(
    query_number: int, args: argparse.Namespace, required_fields: tuple[str, ...]
) -> None:
    missing = [field for field in required_fields if getattr(args, field, None) is None]
    if missing:
        fields = " and ".join(_option_name(field) for field in missing)
        raise ValueError(f"query {query_number} requires {fields}")


def _get_select_specs() -> dict[int, tuple[tuple[str, ...], SelectRunner]]:
    from my_select import (
        advanced_select_1,
        advanced_select_2,
        select_1,
        select_2,
        select_3,
        select_4,
        select_5,
        select_6,
        select_7,
        select_8,
        select_9,
        select_10,
    )

    return {
        1: ((), lambda session, args: select_1(session, limit=args.limit)),
        2: (("subject_id",), lambda session, args: select_2(session, args.subject_id)),
        3: (("subject_id",), lambda session, args: select_3(session, args.subject_id)),
        4: ((), lambda session, args: select_4(session)),
        5: (("teacher_id",), lambda session, args: select_5(session, args.teacher_id)),
        6: (("group_id",), lambda session, args: select_6(session, args.group_id)),
        7: (
            ("group_id", "subject_id"),
            lambda session, args: select_7(session, args.group_id, args.subject_id),
        ),
        8: (("teacher_id",), lambda session, args: select_8(session, args.teacher_id)),
        9: (("student_id",), lambda session, args: select_9(session, args.student_id)),
        10: (
            ("student_id", "teacher_id"),
            lambda session, args: select_10(session, args.student_id, args.teacher_id),
        ),
        11: (
            ("teacher_id", "student_id"),
            lambda session, args: advanced_select_1(
                session, args.teacher_id, args.student_id
            ),
        ),
        12: (
            ("group_id", "subject_id"),
            lambda session, args: advanced_select_2(
                session, args.group_id, args.subject_id
            ),
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HW-06 CLI for CRUD and analytical selects"
    )
    parser.add_argument(
        "-a",
        "--action",
        required=True,
        choices=["create", "list", "update", "remove", "populate", "select"],
    )
    parser.add_argument(
        "-m", "--model", help="Model name: Group, Student, Teacher, Subject, Grade"
    )

    parser.add_argument("--query", type=int, help="Select query number: 1-12")

    parser.add_argument("--id", type=int, help="Entity ID for update/remove")
    parser.add_argument("-n", "--name", help="Name/full name for create/update")
    parser.add_argument("--group-id", type=int, help="Group ID")
    parser.add_argument("--teacher-id", type=int, help="Teacher ID")
    parser.add_argument("--student-id", type=int, help="Student ID")
    parser.add_argument("--subject-id", type=int, help="Subject ID")
    parser.add_argument("--grade", type=int, help="Grade value 1..12")
    parser.add_argument("--date", help="Date in format YYYY-MM-DD")

    parser.add_argument("--limit", type=int, default=5, help="Limit for select_1")
    parser.add_argument("--seed", type=int, help="Optional random seed")
    parser.add_argument(
        "--reset", action="store_true", help="Delete existing data before populate"
    )

    return parser


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _debug_mode_enabled() -> bool:
    return os.getenv("HW06_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}


def _public_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    lowered = message.lower()

    if "password authentication failed" in lowered:
        return "Database authentication failed. Check DATABASE_URL user/password."
    if "connection to server" in lowered or "could not connect" in lowered:
        return "Cannot connect to database server. Check container status and DATABASE_URL."
    if "duplicate key value violates unique constraint" in lowered:
        return "Record already exists (unique constraint violation)."
    if "foreign key" in lowered and "violates" in lowered:
        return "Operation violates foreign key constraint. Check referenced IDs."
    if not message:
        return "Unexpected error"
    return message.split("\n\n")[0]


def run_select(query_number: int, args: argparse.Namespace, session) -> Any:
    select_specs = _get_select_specs()
    spec = select_specs.get(query_number)
    if spec is None:
        raise ValueError("Unknown query number. Use 1..12")

    required_fields, runner = spec
    _validate_required_query_args(query_number, args, required_fields)
    return runner(session, args)


def main() -> None:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()

    LOGGER.info(
        "Starting command: action=%s model=%s query=%s",
        args.action,
        args.model,
        args.query,
    )

    try:
        # Import DB session only after argument parsing so `-h` works without DB driver.
        from conf.db import get_session

        with get_session() as session:
            if args.action in {"create", "list", "update", "remove"}:
                from crud import (
                    create_entity,
                    entity_to_dict,
                    list_entities,
                    remove_entity,
                    update_entity,
                )

                if not args.model:
                    parser.error("CRUD actions require --model")
                if args.action == "create":
                    created = create_entity(session, args.model, args)
                    LOGGER.info(
                        "Entity created: model=%s id=%s", args.model, created.id
                    )
                    _print_json({"status": "created", "data": entity_to_dict(created)})
                elif args.action == "list":
                    rows = list_entities(session, args.model)
                    LOGGER.info(
                        "Entities listed: model=%s count=%s", args.model, len(rows)
                    )
                    _print_json([entity_to_dict(row) for row in rows])
                elif args.action == "update":
                    updated = update_entity(session, args.model, args)
                    LOGGER.info(
                        "Entity updated: model=%s id=%s", args.model, updated.id
                    )
                    _print_json({"status": "updated", "data": entity_to_dict(updated)})
                else:
                    removed_id = remove_entity(session, args.model, args)
                    LOGGER.info(
                        "Entity removed: model=%s id=%s", args.model, removed_id
                    )
                    _print_json(
                        {"status": "removed", "id": removed_id, "model": args.model}
                    )

            elif args.action == "populate":
                from faker_data import populate_database

                summary = populate_database(session, reset=args.reset, seed=args.seed)
                LOGGER.info("Database populated: %s", summary)
                _print_json({"status": "populated", "summary": summary})

            else:
                if args.query is None:
                    parser.error("Select action requires --query (1..12)")
                result = run_select(args.query, args, session)
                if result is None:
                    LOGGER.info("Select returned empty result: query=%s", args.query)
                    _print_json({"status": "empty", "message": "No data found"})
                else:
                    LOGGER.info("Select executed successfully: query=%s", args.query)
                    _print_json(result)

        LOGGER.info("Command finished successfully")

    except Exception as exc:
        debug_mode = _debug_mode_enabled()
        public_message = _public_error_message(exc)

        if debug_mode:
            LOGGER.exception("Command failed")
            _print_json(
                {
                    "status": "error",
                    "message": public_message,
                    "debug_details": str(exc),
                }
            )
        else:
            LOGGER.error("Command failed: %s", public_message)
            _print_json({"status": "error", "message": public_message})
        raise SystemExit(1)


if __name__ == "__main__":
    main()

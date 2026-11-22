"""Command-line layer: argument parsing, clock, JSON output and exit codes."""

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

from smart_todo import domain, storage
from smart_todo.errors import AppError

CLOCK_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
CLOCK_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")

Outcome = tuple[object, domain.Store | None]
Handler = Callable[[argparse.Namespace, domain.Store, str], Outcome]


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser whose failures become a USAGE_ERROR instead of printed usage text."""

    def error(self, message: str) -> NoReturn:
        raise AppError("USAGE_ERROR", message, 2)


def current_time(environ: Mapping[str, str]) -> str:
    """The clock: TODO_NOW when set (validated), otherwise system UTC in whole seconds."""
    override = environ.get("TODO_NOW")
    if override is None:
        return datetime.now(UTC).strftime(CLOCK_FORMAT)
    message = "TODO_NOW must look like 2026-01-01T09:00:00Z."
    if CLOCK_PATTERN.fullmatch(override) is None:
        raise AppError("INVALID_CLOCK", message)
    try:
        datetime.strptime(override, CLOCK_FORMAT)
    except ValueError as error:
        raise AppError("INVALID_CLOCK", message) from error
    return override


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="todo", add_help=False, allow_abbrev=False)
    parser.add_argument("--file", default="todo.json")
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name: str) -> argparse.ArgumentParser:
        return commands.add_parser(name, add_help=False, allow_abbrev=False)

    add = command("add")
    add.add_argument("--title", required=True)
    add.add_argument("--description", default="")
    add.add_argument("--priority", default="medium")
    add.add_argument("--tag", action="append")

    show = command("show")
    show.add_argument("id", type=domain.parse_id)

    listing = command("list")
    listing.add_argument("--status")
    listing.add_argument("--tag", action="append")
    listing.add_argument("--sort", default="id")

    edit = command("edit")
    edit.add_argument("id", type=domain.parse_id)
    edit.add_argument("--title")
    edit.add_argument("--description")
    edit.add_argument("--priority")
    edit.add_argument("--add-tag", action="append")
    edit.add_argument("--remove-tag", action="append")

    status = command("status")
    status.add_argument("id", type=domain.parse_id)
    status.add_argument("new_status")

    delete = command("delete")
    delete.add_argument("id", type=domain.parse_id)
    return parser


def edit_from(args: argparse.Namespace) -> domain.Edit:
    return domain.Edit(
        title=args.title,
        description=args.description,
        priority=args.priority,
        add_tags=tuple(args.add_tag or ()),
        remove_tags=tuple(args.remove_tag or ()),
    )


def check_usage(args: argparse.Namespace) -> None:
    """Usage rules that argparse cannot express (FR-013)."""
    if args.command == "edit" and edit_from(args).is_empty():
        message = "edit needs at least one of --title, --description, --priority, "
        message += "--add-tag, --remove-tag."
        raise AppError("USAGE_ERROR", message, 2)


def cmd_add(args: argparse.Namespace, store: domain.Store, now: str) -> Outcome:
    updated, task = domain.create_task(
        store, args.title, args.description, args.priority, args.tag or [], now
    )
    return task, updated


def cmd_show(args: argparse.Namespace, store: domain.Store, now: str) -> Outcome:
    return domain.find_task(store, args.id), None


def cmd_list(args: argparse.Namespace, store: domain.Store, now: str) -> Outcome:
    tasks = domain.list_tasks(store, args.status, args.tag or [], args.sort)
    return {"tasks": tasks, "count": len(tasks)}, None


def cmd_edit(args: argparse.Namespace, store: domain.Store, now: str) -> Outcome:
    updated, task = domain.edit_task(store, args.id, edit_from(args), now)
    return task, updated


def cmd_status(args: argparse.Namespace, store: domain.Store, now: str) -> Outcome:
    updated, task = domain.change_status(store, args.id, args.new_status, now)
    return task, updated


def cmd_delete(args: argparse.Namespace, store: domain.Store, now: str) -> Outcome:
    return {"deleted": args.id}, domain.delete_task(store, args.id)


HANDLERS: dict[str, Handler] = {
    "add": cmd_add,
    "show": cmd_show,
    "list": cmd_list,
    "edit": cmd_edit,
    "status": cmd_status,
    "delete": cmd_delete,
}


def execute(args: argparse.Namespace) -> object:
    """Run one command: clock, load, domain call, and save only when the store changed."""
    now = current_time(os.environ)
    path = Path(args.file)
    store = storage.load(path)
    payload, updated = HANDLERS[args.command](args, store, now)
    if updated is not None:
        storage.save(path, updated)
    return payload


def emit(stream: object, value: object) -> None:
    """Write one JSON value and a newline as UTF-8 bytes, so output is identical everywhere."""
    data = (json.dumps(value) + "\n").encode("utf-8")
    binary = stream.buffer  # type: ignore[attr-defined]
    binary.write(data)
    binary.flush()


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
        check_usage(args)
        payload = execute(args)
    except AppError as error:
        failure = {"error": {"code": error.code, "message": error.message}}
        emit(sys.stderr, failure)
        return error.exit_code
    emit(sys.stdout, payload)
    return 0

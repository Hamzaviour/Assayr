"""Read a staff list (CSV) for bulk account creation."""

import csv
import io
import re
import secrets
from dataclasses import dataclass

from assayr.identity.rbac import Role
from assayr.identity.security import normalize_email

MAX_ROWS = 2000
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# No look-alike characters (0/O, 1/l/I) so a password read aloud or copied by hand still works.
_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class CsvError(Exception):
    pass


@dataclass
class CsvUser:
    line: int
    full_name: str
    email: str
    department: str | None
    role: str


@dataclass
class CsvProblem:
    line: int
    email: str | None
    reason: str


def temporary_password(length: int = 16) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def parse_users_csv(data: bytes) -> tuple[list[CsvUser], list[CsvProblem]]:
    """Columns by header: name, email, department (optional), role (optional, default employee).

    Accepts what Excel saves: a UTF-8 byte-order mark, comma or semicolon separators, CRLF line ends.
    """
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvError("Save the file as CSV UTF-8 and try again.") from exc
    first = text.splitlines()[0] if text.strip() else ""
    delimiter = ";" if first.count(";") > first.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = [h.strip().lower() for h in next(reader)]
    except StopIteration as exc:
        raise CsvError("The file is empty.") from exc
    if "name" not in header or "email" not in header:
        raise CsvError('The first row must name the columns, including "name" and "email".')
    col = {name: header.index(name) for name in ("name", "email", "department", "role") if name in header}
    roles = {r.value for r in Role}
    users: list[CsvUser] = []
    problems: list[CsvProblem] = []
    seen: set[str] = set()
    for line, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(users) + len(problems) >= MAX_ROWS:
            raise CsvError(f"The file has more than {MAX_ROWS} people. Split it into smaller files.")

        def cell(name: str, row: list[str] = row) -> str:
            index = col.get(name)
            return row[index].strip() if index is not None and index < len(row) else ""

        name, raw_email = cell("name"), cell("email")
        email = normalize_email(raw_email) if raw_email else ""
        role = cell("role").lower() or Role.EMPLOYEE.value
        if not name:
            problems.append(CsvProblem(line, email or None, "The name is missing."))
        elif not _EMAIL.match(email):
            problems.append(CsvProblem(line, raw_email or None, "This is not a valid email address."))
        elif role not in roles:
            problems.append(CsvProblem(line, email, f'"{cell("role")}" is not an Assayr role.'))
        elif email in seen:
            problems.append(CsvProblem(line, email, "This email is already earlier in the file."))
        else:
            seen.add(email)
            users.append(CsvUser(line, name[:200], email, cell("department")[:100] or None, role))
    return users, problems

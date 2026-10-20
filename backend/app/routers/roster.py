import csv
import io
import secrets

from fastapi import APIRouter, Depends, Path, UploadFile, File
from sqlalchemy import text

from ..db import get_conn
from ..deps import require_faculty
from ..errors import AppError
from ..security import hash_password

router = APIRouter(tags=["roster"])


# ---------------------------------------------------------------------------
# CSV parsing helpers
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = {"usn", "name", "section"}
OPTIONAL_COLUMNS = {"pin"}


def _parse_csv(file_content: str):
    """Parse CSV text and return (headers, rows).

    Returns (None, None) if the file is not valid CSV.
    """
    reader = csv.DictReader(io.StringIO(file_content))
    headers = reader.fieldnames or []
    rows = list(reader)
    return headers, rows


def _normalize_row(row: dict, row_num: int):
    """Validate a single CSV row. Returns (valid_tuple, bad_tuple).

    valid_tuple: (row_num, usn, name, section, pin_or_None)
    bad_tuple: (row_num, usn, reason)
    """
    usn = (row.get("usn") or "").strip()
    name = (row.get("name") or "").strip()
    section = (row.get("section") or "").strip() or "A"
    pin = (row.get("pin") or "").strip()

    # Normalize USN
    norm_usn = usn.upper()

    if not usn:
        return None, (row_num, usn or "", "missing usn")
    if not name:
        return None, (row_num, norm_usn, "missing name")

    # Validate pin if provided
    if pin:
        if not (pin.isdigit() and len(pin) == 6):
            return None, (row_num, norm_usn, "pin must be 6 digits")

    return (row_num, norm_usn, name, section, pin or None), None


def _analyze_rows(rows: list[dict]):
    """Run the full analysis and return the preview structure."""
    bad_rows = []
    valid_rows = []
    seen_usns: dict[str, list[int]] = {}  # usn -> row numbers

    for idx, row in enumerate(rows, start=2):  # row 1 is header
        valid, bad = _normalize_row(row, idx)
        if bad is not None:
            bad_rows.append({"row": bad[0], "usn": bad[1], "reason": bad[2]})
        else:
            row_num, usn, name, section, pin = valid
            valid_rows.append(valid)
            seen_usns.setdefault(usn, []).append(row_num)

    # Split valid rows: first occurrence valid, subsequent are duplicates
    unique_valid = []
    duplicates_in_file = []
    seen: set[str] = set()
    for v in valid_rows:
        row_num, usn, name, section, pin = v
        if usn in seen:
            continue
        seen.add(usn)
        unique_valid.append(v)
        if len(seen_usns[usn]) > 1:
            duplicates_in_file.append({"usn": usn, "rows": seen_usns[usn]})

    return {
        "total_rows": len(rows),
        "valid": [
            {"row": v[0], "usn": v[1], "name": v[2], "section": v[3]}
            for v in unique_valid
        ],
        "bad_rows": bad_rows,
        "duplicates_in_file": duplicates_in_file,
        "valid_parsed": unique_valid,
    }


# ---------------------------------------------------------------------------
# Ownership check
# ---------------------------------------------------------------------------

def _subject_owned(conn, subject_id: str, faculty_user_id: str):
    row = conn.execute(
        text("SELECT id FROM subjects WHERE id = :id AND faculty_user_id = :fid"),
        {"id": subject_id, "fid": faculty_user_id},
    ).mappings().fetchone()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Subject not found")
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/subjects/{id}/roster/preview")
def preview_roster(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    file: UploadFile = File(..., alias="file"),
):
    _subject_owned(conn, id, faculty["user_id"])

    content = file.file.read().decode("utf-8-sig")
    headers, rows = _parse_csv(content)

    # Check required columns
    for col in REQUIRED_COLUMNS:
        if col not in headers:
            raise AppError(400, "BAD_REQUEST", f"CSV missing required column: {col}")

    analysis = _analyze_rows(rows)

    # Check already enrolled
    valid_usns = [v[1] for v in analysis["valid_parsed"]]
    already_enrolled = []
    if valid_usns:
        placeholders = ", ".join(f"'{u}'" for u in valid_usns)
        enrolled = conn.execute(
            text(
                f"SELECT DISTINCT s.usn FROM enrollments e "
                f"JOIN students s ON s.id = e.student_id "
                f"WHERE e.subject_id = :sid AND s.usn IN ({placeholders})"
            ),
            {"sid": id},
        ).mappings().fetchall()
        already_enrolled = [r["usn"] for r in enrolled]

    # Remove the internal key before returning
    del analysis["valid_parsed"]
    analysis["already_enrolled"] = already_enrolled
    return analysis


@router.post("/subjects/{id}/roster")
def confirm_roster(
    id: str = Path(..., alias="id"),
    conn=Depends(get_conn),
    faculty=Depends(require_faculty),
    file: UploadFile = File(..., alias="file"),
):
    _subject_owned(conn, id, faculty["user_id"])

    content = file.file.read().decode("utf-8-sig")
    headers, rows = _parse_csv(content)

    for col in REQUIRED_COLUMNS:
        if col not in headers:
            raise AppError(400, "BAD_REQUEST", f"CSV missing required column: {col}")

    analysis = _analyze_rows(rows)
    valid_rows = analysis["valid_parsed"]

    # Check already enrolled
    valid_usns = [v[1] for v in valid_rows]
    already_enrolled = []
    if valid_usns:
        placeholders = ", ".join(f"'{u}'" for u in valid_usns)
        enrolled = conn.execute(
            text(
                f"SELECT DISTINCT s.usn FROM enrollments e "
                f"JOIN students s ON s.id = e.student_id "
                f"WHERE e.subject_id = :sid AND s.usn IN ({placeholders})"
            ),
            {"sid": id},
        ).mappings().fetchall()
        already_enrolled = [r["usn"] for r in enrolled]
    already_enrolled_set = set(already_enrolled)

    created_students = 0
    created_enrollments = 0
    skipped = []
    credentials = []

    for row_num, usn, name, section, pin in valid_rows:
        # Check if student already exists
        existing = conn.execute(
            text("SELECT id, pin_hash FROM students WHERE usn = :usn"),
            {"usn": usn},
        ).mappings().fetchone()

        if existing is not None:
            student_id = str(existing["id"])
            # Enroll if not already enrolled
            if usn in already_enrolled_set:
                skipped.append({"row": row_num, "usn": usn, "reason": "already enrolled"})
            else:
                conn.execute(
                    text(
                        "INSERT INTO enrollments (student_id, subject_id, section) "
                        "VALUES (:sid, :subj, :sec)"
                    ),
                    {"sid": student_id, "subj": id, "sec": section},
                )
                created_enrollments += 1
            # Existing student keeps their PIN — never returned
        else:
            # Generate or use provided PIN
            if pin is None:
                pin = str(secrets.randbelow(900000) + 100000)  # 6-digit

            pin_hash = hash_password(pin)

            # Create student
            result = conn.execute(
                text(
                    "INSERT INTO students (usn, name, pin_hash) "
                    "VALUES (:usn, :name, :ph) RETURNING id"
                ),
                {"usn": usn, "name": name, "ph": pin_hash},
            )
            student_id = str(result.mappings().fetchone()["id"])
            created_students += 1

            # Create users row (role student)
            conn.execute(
                text(
                    "INSERT INTO users (role, student_id) VALUES ('student', :sid)"
                ),
                {"sid": student_id},
            )

            # Enroll
            conn.execute(
                text(
                    "INSERT INTO enrollments (student_id, subject_id, section) "
                    "VALUES (:sid, :subj, :sec)"
                ),
                {"sid": student_id, "subj": id, "sec": section},
            )
            created_enrollments += 1
            credentials.append({"usn": usn, "pin": pin})

    # Add bad rows and duplicates to skipped
    for br in analysis["bad_rows"]:
        skipped.append({"row": br["row"], "usn": br["usn"], "reason": br["reason"]})
    for dup in analysis["duplicates_in_file"]:
        for r in dup["rows"][1:]:  # skip first occurrence (it's valid)
            skipped.append({"row": r, "usn": dup["usn"], "reason": "duplicate in file"})

    return {
        "created_students": created_students,
        "created_enrollments": created_enrollments,
        "skipped": skipped,
        "credentials": credentials,
    }

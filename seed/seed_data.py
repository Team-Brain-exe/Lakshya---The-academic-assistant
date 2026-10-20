"""Synthetic seed data generator for Lakshya — The Academic Assistant.

Follows the schema in backend/migrations/001_init.sql and the rules in arya.md:
- 1 subject (CS201 Data Structures and Algorithms)
- 6 Course Outcomes (CO1 to CO6) with 60% threshold and 60% target
- 4 Modules
- 60 synthetic students with fake USNs (1XX23CS001 to 1XX23CS060)
- Realistic score spread across Section A and Section B
- A cohort clearly weak in CO3 (so find_weak_COs flags CO3)
- 2 published quizzes with approved questions (4 options, 1 correct)
- Deterministic quiz attempts and StudentCOScore calculations matching grading.py

Never commit real student data or credentials.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.engine.co_math import (
    AttemptScore,
    COConfig,
    StudentInfo,
    build_co_sheet,
    class_summary,
    select_counted,
    weak_cos,
)
from app.engine.grading import QuestionKey, grade_attempt

# Deterministic UUID generator based on namespace and seed key
_SEED_NAMESPACE = uuid.UUID("a7e584f2-9c12-4e89-b781-64d1f2b4c810")


def deterministic_uuid(key: str) -> str:
    """Generate a reproducible UUID5 string from a unique key."""
    return str(uuid.uuid5(_SEED_NAMESPACE, key))


# Simple dummy bcrypt-like hash for synthetic PIN "123456"
SYNTHETIC_PIN_HASH = "$2b$12$e80yq7hFvQ77uM2F1qE8O.sC8s4rD/W14G5K7U6dJ2z.pXqO2rKyi"
SYNTHETIC_PASSWORD_HASH = "$2b$12$v9XoG5CqS77uM2F1qE8O.sC8s4rD/W14G5K7U6dJ2z.pXqO2rKyi"


@dataclass(frozen=True)
class SeedData:
    faculty_user: dict[str, Any]
    subject: dict[str, Any]
    cos: list[dict[str, Any]]
    modules: list[dict[str, Any]]
    content_chunks: list[dict[str, Any]]
    chunk_cos: list[dict[str, Any]]
    students: list[dict[str, Any]]
    users: list[dict[str, Any]]
    enrollments: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    quizzes: list[dict[str, Any]]
    quiz_questions: list[dict[str, Any]]
    quiz_attempts: list[dict[str, Any]]
    student_co_scores: list[dict[str, Any]]


_FIRST_NAMES = [
    "Aarav", "Aditi", "Akash", "Ananya", "Ankit", "Aparna", "Arjun", "Arya", "Bhavya", "Chetan",
    "Deepak", "Dev", "Divya", "Gaurav", "Harsh", "Isha", "Ishaan", "Kavya", "Karan", "Kunal",
    "Lakshmi", "Manish", "Meera", "Mohit", "Neha", "Nikhil", "Nisha", "Pooja", "Pranav", "Priya",
    "Rahul", "Rakesh", "Riya", "Rohan", "Rohit", "Sachin", "Sahil", "Sakshi", "Sameer", "Sanjay",
    "Shreya", "Siddharth", "Simran", "Sneha", "Soham", "Sonali", "Sparsh", "Suman", "Suraj", "Swati",
    "Tanvi", "Tarun", "Utkarsh", "Vaibhav", "Varun", "Vedant", "Vidya", "Vikram", "Yash", "Zara",
]

_LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Reddy", "Nair", "Iyer", "Rao", "Kulkarni", "Deshmukh", "Joshi",
    "Gupta", "Bhat", "Mehta", "Chopra", "Das", "Menon", "Pillai", "Hegde", "Kumar", "Singh",
]


def _student_name(idx: int) -> str:
    fname = _FIRST_NAMES[(idx - 1) % len(_FIRST_NAMES)]
    lname = _LAST_NAMES[((idx - 1) * 3) % len(_LAST_NAMES)]
    return f"{fname} {lname}"


def generate_seed_data() -> SeedData:
    """Generate deterministic synthetic seed data for CS201 Data Structures."""
    now_iso = "2026-10-01T09:00:00Z"

    # Faculty User
    faculty_user_id = deterministic_uuid("faculty:dr_raman")
    faculty_user = {
        "id": faculty_user_id,
        "role": "faculty",
        "email": "raman@lakshya.edu",
        "name": "Dr. C. V. Raman",
        "password_hash": SYNTHETIC_PASSWORD_HASH,
        "created_at": now_iso,
    }

    # Subject
    subject_id = deterministic_uuid("subject:CS201")
    subject = {
        "id": subject_id,
        "code": "CS201",
        "name": "Data Structures and Algorithms",
        "semester": 3,
        "faculty_user_id": faculty_user_id,
        "target_attainment_pct": 60.0,
        "default_threshold_pct": 60.0,
        "created_at": now_iso,
    }

    # 6 Course Outcomes
    co_descriptions = [
        "Analyze asymptotic time and space complexity of fundamental algorithms",
        "Implement and apply linear data structures: stacks, queues, and linked lists",
        "Construct and balance non-linear hierarchical data structures: binary trees, BSTs, and heaps",
        "Design graph representations and execute traversal algorithms (BFS and DFS)",
        "Analyze collision resolution techniques and efficiency in hash tables",
        "Evaluate sorting and searching paradigms for diverse operational constraints",
    ]
    cos = []
    for co_num, desc in enumerate(co_descriptions, start=1):
        cos.append({
            "id": deterministic_uuid(f"co:{subject_id}:{co_num}"),
            "subject_id": subject_id,
            "number": co_num,
            "description": desc,
            "threshold_pct": 60.0,
            "target_attainment_pct": 60.0,
            "created_at": now_iso,
        })

    # 4 Modules
    module_titles = [
        "Algorithm Analysis & Linear Data Structures",
        "Stacks, Queues, and Linked Lists Applications",
        "Trees, Binary Search Trees, and Heaps",
        "Graph Algorithms & Hash Tables",
    ]
    modules = []
    for m_num, title in enumerate(module_titles, start=1):
        modules.append({
            "id": deterministic_uuid(f"module:{subject_id}:{m_num}"),
            "subject_id": subject_id,
            "number": m_num,
            "title": title,
            "ppt_file_path": f"/uploads/cs201_module_{m_num}.pptx",
            "processing_status": "done",
            "processing_error": None,
            "processed_at": now_iso,
            "created_at": now_iso,
        })

    # Content Chunks & Chunk CO links (sample slides for retrieval / study plan grounding)
    sample_slides = [
        # Module 1
        (1, 1, "Asymptotic Notations: Big-O, Big-Omega, Big-Theta definitions and growth rates.", [1]),
        (1, 2, "Space complexity analysis of iterative versus recursive functions.", [1]),
        (1, 3, "Static vs Dynamic arrays: contiguous memory allocation and resizing amortized cost.", [1, 2]),
        # Module 2
        (2, 1, "Stack ADT: LIFO principle, push, pop, and expression evaluation using stacks.", [2]),
        (2, 2, "Queue ADT: FIFO principle, circular queue implementation and boundary conditions.", [2]),
        (2, 3, "Singly and Doubly Linked Lists: pointer manipulations and insertion/deletion bounds.", [2]),
        # Module 3
        (3, 1, "Binary Trees: properties, representations, and in-order, pre-order, post-order traversals.", [3]),
        (3, 2, "Binary Search Trees (BST): search, insertion, and deletion algorithms with complexity.", [3]),
        (3, 3, "Binary Heaps and Priority Queues: max-heapify, insert, extract-max operations.", [3]),
        # Module 4
        (4, 1, "Graph Representations: Adjacency Matrix vs Adjacency List tradeoffs.", [4]),
        (4, 2, "Breadth-First Search (BFS) and Depth-First Search (DFS) implementation and paths.", [4]),
        (4, 3, "Hash Tables: hash functions, separate chaining, and open addressing probing methods.", [5]),
        (4, 4, "Comparison of sorting algorithms: QuickSort, MergeSort, and HeapSort stability and bounds.", [6]),
    ]
    content_chunks = []
    chunk_cos = []
    for mod_idx, slide_num, text, co_nums in sample_slides:
        mod_id = modules[mod_idx - 1]["id"]
        c_id = deterministic_uuid(f"chunk:{mod_id}:{slide_num}")
        content_chunks.append({
            "id": c_id,
            "module_id": mod_id,
            "slide_number": slide_num,
            "text": text,
            "tag_status": "tagged",
            "created_at": now_iso,
        })
        for cnum in co_nums:
            co_id = cos[cnum - 1]["id"]
            chunk_cos.append({
                "chunk_id": c_id,
                "co_id": co_id,
                "confidence": 0.95,
            })

    # 60 Synthetic Students (USN: 1XX23CS001 .. 1XX23CS060)
    students = []
    users = []
    enrollments = []
    for i in range(1, 61):
        usn = f"1XX23CS{i:03d}"
        s_id = deterministic_uuid(f"student:{usn}")
        u_id = deterministic_uuid(f"user:{usn}")
        name = _student_name(i)
        section = "A" if i <= 30 else "B"

        students.append({
            "id": s_id,
            "usn": usn,
            "name": name,
            "pin_hash": SYNTHETIC_PIN_HASH,
            "created_at": now_iso,
        })
        users.append({
            "id": u_id,
            "role": "student",
            "email": None,
            "name": name,
            "password_hash": None,
            "student_id": s_id,
            "created_at": now_iso,
        })
        enrollments.append({
            "id": deterministic_uuid(f"enrollment:{s_id}:{subject_id}"),
            "student_id": s_id,
            "subject_id": subject_id,
            "section": section,
            "created_at": now_iso,
        })

    # Approved Questions for 2 Quizzes
    # Quiz 1: Module 1 & 2 covering CO1 and CO2 (5 questions)
    # Quiz 2: Module 3 covering CO3 (5 questions)
    raw_questions = [
        # Quiz 1 questions (Q1-Q5)
        (
            1, 1, 1,  # mod 1, co 1
            "What is the tightest upper bound time complexity of binary search on a sorted array of n elements?",
            ["O(1)", "O(log n)", "O(n)", "O(n log n)"],
            1,
            "Binary search halves the search space at each comparison step, yielding O(log n) time.",
            "easy", "remember",
        ),
        (
            1, 1, 1,  # mod 1, co 1
            "Which asymptotic notation represents both an asymptotic upper and lower bound simultaneously?",
            ["Big-O", "Big-Omega", "Big-Theta", "Little-o"],
            2,
            "Big-Theta denotes an asymptotically tight bound (both upper and lower).",
            "medium", "understand",
        ),
        (
            1, 2, 2,  # mod 2, co 2
            "Which data structure operates on a Last-In-First-Out (LIFO) order?",
            ["Queue", "Stack", "Priority Queue", "Deque"],
            1,
            "A stack is defined by LIFO operations where the last inserted element is removed first.",
            "easy", "remember",
        ),
        (
            1, 2, 2,  # mod 2, co 2
            "In an optimal circular queue implementation with an array of size N, how are indices advanced?",
            ["(index + 1)", "(index + 1) % N", "index + N", "(index - 1) % N"],
            1,
            "Modulo arithmetic wraps the index back to 0 when it reaches the array boundary N.",
            "medium", "apply",
        ),
        (
            1, 2, 2,  # mod 2, co 2
            "What is the time complexity of deleting a node given only a pointer to it in a doubly linked list?",
            ["O(n)", "O(log n)", "O(1)", "O(n^2)"],
            2,
            "A doubly linked list allows updating adjacent pointers directly in O(1) time.",
            "medium", "understand",
        ),
        # Quiz 2 questions (Q6-Q10) - CO3 Trees & BSTs
        (
            3, 3, 3,  # mod 3, co 3
            "What is the maximum number of nodes in a binary tree of depth k (root is at depth 1)?",
            ["2^k", "2^k - 1", "2^(k-1)", "2^(k+1) - 1"],
            1,
            "A binary tree has at most 2^k - 1 nodes across k levels.",
            "medium", "understand",
        ),
        (
            3, 3, 3,  # mod 3, co 3
            "In an in-order traversal of a valid Binary Search Tree (BST), what property holds for the visit sequence?",
            ["Elements are sorted in ascending order", "Elements are sorted in descending order", "Elements appear by depth level", "Leaves are visited first"],
            0,
            "In-order traversal (Left, Root, Right) processes BST nodes in strictly non-decreasing order.",
            "easy", "understand",
        ),
        (
            3, 3, 3,  # mod 3, co 3
            "What is the worst-case time complexity of searching an element in an unbalanced skewed BST?",
            ["O(log n)", "O(1)", "O(n)", "O(n log n)"],
            2,
            "A degenerate or skewed BST degenerates into a singly linked list with O(n) worst-case search.",
            "medium", "analyze",
        ),
        (
            3, 3, 3,  # mod 3, co 3
            "In a max-heap stored in a 1-indexed array, where is the parent of the node at index i located?",
            ["2 * i", "2 * i + 1", "floor(i / 2)", "i - 1"],
            2,
            "In a 1-indexed binary heap array, the parent of index i is at floor(i / 2).",
            "medium", "apply",
        ),
        (
            3, 3, 3,  # mod 3, co 3
            "Which of the following operations takes O(log n) time in a binary min-heap with n elements?",
            ["Find minimum", "Extract minimum", "Build heap from unordered array", "Read root value"],
            1,
            "Extracting minimum removes the root and requires sift-down heapify taking O(log n) time.",
            "hard", "analyze",
        ),
    ]

    questions = []
    for idx, (m_num, co_num, c_number, stem, opts, corr, expl, diff, bloom) in enumerate(raw_questions, start=1):
        q_id = deterministic_uuid(f"question:cs201:{idx}")
        questions.append({
            "id": q_id,
            "module_id": modules[m_num - 1]["id"],
            "co_id": cos[co_num - 1]["id"],
            "co_number": c_number,
            "stem": stem,
            "options": opts,
            "correct_option": corr,
            "explanation": expl,
            "marks": 1.0,
            "difficulty": diff,
            "bloom_level": bloom,
            "status": "approved",
            "source": "faculty",
            "created_by": faculty_user_id,
            "created_at": now_iso,
        })

    # Quizzes
    quiz1_id = deterministic_uuid("quiz:cs201:1")
    quiz2_id = deterministic_uuid("quiz:cs201:2")

    quizzes = [
        {
            "id": quiz1_id,
            "module_id": modules[0]["id"],
            "subject_id": subject_id,
            "title": "Quiz 1: Complexity & Linear Data Structures",
            "opens_at": "2026-10-05T09:00:00Z",
            "closes_at": "2026-10-12T23:59:59Z",
            "published": True,
            "published_at": "2026-10-05T08:00:00Z",
            "created_by": faculty_user_id,
            "created_at": now_iso,
        },
        {
            "id": quiz2_id,
            "module_id": modules[2]["id"],
            "subject_id": subject_id,
            "title": "Quiz 2: Trees, BSTs and Heaps",
            "opens_at": "2026-10-15T09:00:00Z",
            "closes_at": "2026-10-22T23:59:59Z",
            "published": True,
            "published_at": "2026-10-15T08:00:00Z",
            "created_by": faculty_user_id,
            "created_at": now_iso,
        },
    ]

    quiz_questions = []
    # Quiz 1 has Q1-Q5
    for pos, q in enumerate(questions[:5]):
        quiz_questions.append({
            "quiz_id": quiz1_id,
            "question_id": q["id"],
            "position": pos + 1,
        })
    # Quiz 2 has Q6-Q10
    for pos, q in enumerate(questions[5:]):
        quiz_questions.append({
            "quiz_id": quiz2_id,
            "question_id": q["id"],
            "position": pos + 1,
        })

    # Question keys for deterministic grading
    qkeys1 = [
        QuestionKey(id=q["id"], co=q["co_number"], correct_option=q["correct_option"], marks=q["marks"])
        for q in questions[:5]
    ]
    qkeys2 = [
        QuestionKey(id=q["id"], co=q["co_number"], correct_option=q["correct_option"], marks=q["marks"])
        for q in questions[5:]
    ]

    # Generate Student Attempts with realistic spread and weak CO3 cohort
    # Cohort weak in CO3: students with index 35 to 60 (Section B, ~26 students)
    # perform poorly on Quiz 2 (only 0 or 1 question correct out of 5 -> 0% to 20%).
    # This guarantees CO3 class attainment is under 60% target!
    quiz_attempts = []
    student_co_scores = []

    for idx, s in enumerate(students, start=1):
        usn = s["usn"]
        s_id = s["id"]

        # --- Quiz 1 Attempt (All students attempt Quiz 1) ---
        # Good distribution: most get 4 or 5 right, a few get 2 or 3.
        # Deterministic score pattern based on student index
        q1_answers: dict[str, int] = {}
        for q_idx, qk in enumerate(qkeys1):
            # student gets question correct unless their index matches condition
            is_correct = (idx + q_idx) % 7 != 0
            ans = qk.correct_option if is_correct else (qk.correct_option + 1) % 4
            q1_answers[qk.id] = ans

        g1 = grade_attempt(qkeys1, q1_answers)
        att1_id = deterministic_uuid(f"attempt:{s_id}:{quiz1_id}:1")
        quiz_attempts.append({
            "id": att1_id,
            "quiz_id": quiz1_id,
            "student_id": s_id,
            "attempt_number": 1,
            "answers": q1_answers,
            "total_score": g1.total_obtained,
            "max_score": g1.total_max,
            "started_at": "2026-10-06T10:00:00Z",
            "submitted_at": "2026-10-06T10:25:00Z",
            "created_at": now_iso,
        })
        for co_num, cm in g1.per_co.items():
            co_id = cos[co_num - 1]["id"]
            student_co_scores.append({
                "id": deterministic_uuid(f"coscore:{att1_id}:{co_id}"),
                "student_id": s_id,
                "subject_id": subject_id,
                "module_id": modules[0]["id"],
                "co_id": co_id,
                "attempt_id": att1_id,
                "marks_obtained": cm.obtained,
                "max_marks": cm.maximum,
                "percentage": cm.percentage,
                "counted": True,
                "created_at": now_iso,
            })

        # --- Quiz 2 Attempt (Module 3 / CO3) ---
        # If student index >= 35, they struggle on CO3 (weak cohort)
        # They score at most 1 / 5 (20%), failing the 60% threshold.
        # Students 1 to 34 score well (3 to 5 correct).
        # A couple students skip attempt (e.g. index 59 and 60)
        if idx in (59, 60):
            continue  # unattempted edge case for summary

        q2_answers: dict[str, int] = {}
        is_weak_student = idx >= 35

        for q_idx, qk in enumerate(qkeys2):
            if is_weak_student:
                # only get question 0 right, rest wrong
                is_correct = (q_idx == 0 and idx % 2 == 0)
            else:
                is_correct = (idx + q_idx) % 5 != 0

            ans = qk.correct_option if is_correct else (qk.correct_option + 1) % 4
            q2_answers[qk.id] = ans

        g2 = grade_attempt(qkeys2, q2_answers)
        att2_id = deterministic_uuid(f"attempt:{s_id}:{quiz2_id}:1")
        quiz_attempts.append({
            "id": att2_id,
            "quiz_id": quiz2_id,
            "student_id": s_id,
            "attempt_number": 1,
            "answers": q2_answers,
            "total_score": g2.total_obtained,
            "max_score": g2.total_max,
            "started_at": "2026-10-16T14:00:00Z",
            "submitted_at": "2026-10-16T14:28:00Z",
            "created_at": now_iso,
        })
        for co_num, cm in g2.per_co.items():
            co_id = cos[co_num - 1]["id"]
            student_co_scores.append({
                "id": deterministic_uuid(f"coscore:{att2_id}:{co_id}"),
                "student_id": s_id,
                "subject_id": subject_id,
                "module_id": modules[2]["id"],
                "co_id": co_id,
                "attempt_id": att2_id,
                "marks_obtained": cm.obtained,
                "max_marks": cm.maximum,
                "percentage": cm.percentage,
                "counted": True,
                "created_at": now_iso,
            })

    return SeedData(
        faculty_user=faculty_user,
        subject=subject,
        cos=cos,
        modules=modules,
        content_chunks=content_chunks,
        chunk_cos=chunk_cos,
        students=students,
        users=users,
        enrollments=enrollments,
        questions=questions,
        quizzes=quizzes,
        quiz_questions=quiz_questions,
        quiz_attempts=quiz_attempts,
        student_co_scores=student_co_scores,
    )


def generate_sql(seed: SeedData) -> str:
    """Format SeedData as raw PostgreSQL INSERT statements matching 001_init.sql."""
    lines: list[str] = [
        "-- Synthetic seed data for Lakshya Academic Assistant",
        "-- Safe to run on clean database with 001_init.sql and 003_user_name.sql applied.",
        "BEGIN;",
        "",
    ]

    def esc(val: Any) -> str:
        if val is None:
            return "NULL"
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, bool):
            return "TRUE" if val else "FALSE"
        if isinstance(val, (dict, list)):
            return "'" + json.dumps(val).replace("'", "''") + "'::jsonb"
        s = str(val).replace("'", "''")
        return f"'{s}'"

    # 1. Faculty user
    u = seed.faculty_user
    lines.append(
        f"INSERT INTO users (id, role, email, password_hash, name, created_at) "
        f"VALUES ({esc(u['id'])}, {esc(u['role'])}, {esc(u['email'])}, {esc(u['password_hash'])}, {esc(u['name'])}, {esc(u['created_at'])}) "
        f"ON CONFLICT (id) DO NOTHING;"
    )

    # 2. Subject
    sb = seed.subject
    lines.append(
        f"INSERT INTO subjects (id, code, name, semester, faculty_user_id, target_attainment_pct, default_threshold_pct, created_at) "
        f"VALUES ({esc(sb['id'])}, {esc(sb['code'])}, {esc(sb['name'])}, {esc(sb['semester'])}, {esc(sb['faculty_user_id'])}, {esc(sb['target_attainment_pct'])}, {esc(sb['default_threshold_pct'])}, {esc(sb['created_at'])}) "
        f"ON CONFLICT (id) DO NOTHING;"
    )

    # 3. Course Outcomes
    for c in seed.cos:
        lines.append(
            f"INSERT INTO course_outcomes (id, subject_id, number, description, threshold_pct, target_attainment_pct, created_at) "
            f"VALUES ({esc(c['id'])}, {esc(c['subject_id'])}, {esc(c['number'])}, {esc(c['description'])}, {esc(c['threshold_pct'])}, {esc(c['target_attainment_pct'])}, {esc(c['created_at'])}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )

    # 4. Modules
    for m in seed.modules:
        lines.append(
            f"INSERT INTO modules (id, subject_id, number, title, ppt_file_path, processing_status, processed_at, created_at) "
            f"VALUES ({esc(m['id'])}, {esc(m['subject_id'])}, {esc(m['number'])}, {esc(m['title'])}, {esc(m['ppt_file_path'])}, {esc(m['processing_status'])}, {esc(m['processed_at'])}, {esc(m['created_at'])}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )

    # 5. Content Chunks & Chunk COs
    for ch in seed.content_chunks:
        lines.append(
            f"INSERT INTO content_chunks (id, module_id, slide_number, text, tag_status, created_at) "
            f"VALUES ({esc(ch['id'])}, {esc(ch['module_id'])}, {esc(ch['slide_number'])}, {esc(ch['text'])}, {esc(ch['tag_status'])}, {esc(ch['created_at'])}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )
    for cco in seed.chunk_cos:
        lines.append(
            f"INSERT INTO chunk_cos (chunk_id, co_id, confidence) "
            f"VALUES ({esc(cco['chunk_id'])}, {esc(cco['co_id'])}, {esc(cco['confidence'])}) "
            f"ON CONFLICT (chunk_id, co_id) DO NOTHING;"
        )

    # 6. Students, Student Users, Enrollments
    for s in seed.students:
        lines.append(
            f"INSERT INTO students (id, usn, name, pin_hash, created_at) "
            f"VALUES ({esc(s['id'])}, {esc(s['usn'])}, {esc(s['name'])}, {esc(s['pin_hash'])}, {esc(s['created_at'])}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )
    for su in seed.users:
        lines.append(
            f"INSERT INTO users (id, role, name, student_id, created_at) "
            f"VALUES ({esc(su['id'])}, {esc(su['role'])}, {esc(su['name'])}, {esc(su['student_id'])}, {esc(su['created_at'])}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )
    for en in seed.enrollments:
        lines.append(
            f"INSERT INTO enrollments (id, student_id, subject_id, section, created_at) "
            f"VALUES ({esc(en['id'])}, {esc(en['student_id'])}, {esc(en['subject_id'])}, {esc(en['section'])}, {esc(en['created_at'])}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )

    # 7. Questions
    for q in seed.questions:
        lines.append(
            f"INSERT INTO questions (id, module_id, co_id, stem, options, correct_option, explanation, marks, difficulty, bloom_level, status, source, created_by, created_at) "
            f"VALUES ({esc(q['id'])}, {esc(q['module_id'])}, {esc(q['co_id'])}, {esc(q['stem'])}, {esc(q['options'])}, {esc(q['correct_option'])}, {esc(q['explanation'])}, {esc(q['marks'])}, {esc(q['difficulty'])}, {esc(q['bloom_level'])}, {esc(q['status'])}, {esc(q['source'])}, {esc(q['created_by'])}, {esc(q['created_at'])}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )

    # 8. Quizzes & Quiz Questions
    for qz in seed.quizzes:
        lines.append(
            f"INSERT INTO quizzes (id, module_id, subject_id, title, opens_at, closes_at, published, published_at, created_by, created_at) "
            f"VALUES ({esc(qz['id'])}, {esc(qz['module_id'])}, {esc(qz['subject_id'])}, {esc(qz['title'])}, {esc(qz['opens_at'])}, {esc(qz['closes_at'])}, {esc(qz['published'])}, {esc(qz['published_at'])}, {esc(qz['created_by'])}, {esc(qz['created_at'])}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )
    for qq in seed.quiz_questions:
        lines.append(
            f"INSERT INTO quiz_questions (quiz_id, question_id, position) "
            f"VALUES ({esc(qq['quiz_id'])}, {esc(qq['question_id'])}, {esc(qq['position'])}) "
            f"ON CONFLICT (quiz_id, question_id) DO NOTHING;"
        )

    # 9. Quiz Attempts & Student CO Scores
    for qa in seed.quiz_attempts:
        lines.append(
            f"INSERT INTO quiz_attempts (id, quiz_id, student_id, attempt_number, answers, total_score, max_score, started_at, submitted_at, created_at) "
            f"VALUES ({esc(qa['id'])}, {esc(qa['quiz_id'])}, {esc(qa['student_id'])}, {esc(qa['attempt_number'])}, {esc(qa['answers'])}, {esc(qa['total_score'])}, {esc(qa['max_score'])}, {esc(qa['started_at'])}, {esc(qa['submitted_at'])}, {esc(qa['created_at'])}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )
    for sc in seed.student_co_scores:
        lines.append(
            f"INSERT INTO student_co_scores (id, student_id, subject_id, module_id, co_id, attempt_id, marks_obtained, max_marks, percentage, counted, created_at) "
            f"VALUES ({esc(sc['id'])}, {esc(sc['student_id'])}, {esc(sc['subject_id'])}, {esc(sc['module_id'])}, {esc(sc['co_id'])}, {esc(sc['attempt_id'])}, {esc(sc['marks_obtained'])}, {esc(sc['max_marks'])}, {esc(sc['percentage'])}, {esc(sc['counted'])}, {esc(sc['created_at'])}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )

    lines.append("COMMIT;")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate synthetic seed data")
    parser.add_argument("--sql", action="store_true", help="Print SQL statements")
    args = parser.parse_args()

    data = generate_seed_data()
    if args.sql:
        print(generate_sql(data))
    else:
        print(f"Generated synthetic seed data:")
        print(f"  Subject: {data.subject['code']} - {data.subject['name']}")
        print(f"  COs: {len(data.cos)}")
        print(f"  Modules: {len(data.modules)}")
        print(f"  Students: {len(data.students)}")
        print(f"  Quizzes: {len(data.quizzes)}")
        print(f"  Questions: {len(data.questions)}")
        print(f"  Attempts: {len(data.quiz_attempts)}")
        print(f"  Student CO Scores: {len(data.student_co_scores)}")


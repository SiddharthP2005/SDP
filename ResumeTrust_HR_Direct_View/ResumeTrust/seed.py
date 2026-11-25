"""
Seed demo users, academic records and a placement drive. Students upload demo PDFs interactively.
"""

import os
from pathlib import Path
from database import init_db, get_connection, add_audit_log
from auth import register_user

DEMO_DIR = Path(__file__).parent / "demo_resumes"


def seed():
    # Reset DB for clean demo
    db_path = Path(__file__).parent / "resumetrust.db"
    if db_path.exists():
        db_path.unlink()

    init_db()

    print("Creating demo users...")

    # 1. Placement Cell Officer
    placement_id = register_user(
        email="placement@college.edu",
        password="Placement@123",
        full_name="Dr. Anita Desai",
        role="placement",
        college="National Institute of Technology",
    )

    # 2. Company HR
    hr_id = register_user(
        email="hr@techcorp.com",
        password="HR@Tech123",
        full_name="Vikram Singh",
        role="hr",
        company="TechCorp Solutions",
    )

    # 3. Students
    students = [
        {
            "email": "arjun.sharma@college.edu",
            "password": "Student@123",
            "full_name": "Arjun Sharma",
            "student_id": "CS2022-041",
            "college": "National Institute of Technology, Karnataka",
            "resume_file": "demo_resume_arjun_sharma.pdf",
            "academics": {
                "tenth_percentage": 96.0,
                "twelfth_percentage": 94.2,
                "degree_cgpa": 8.72,
                "degree_name": "B.Tech CSE",
                "branch": "Computer Science & Engineering",
                "year_of_passing": 2026,
            },
        },
        {
            "email": "priya.patel@college.edu",
            "password": "Student@123",
            "full_name": "Priya Patel",
            "student_id": "IT2022-018",
            "college": "Nirma University",
            "resume_file": "demo_resume_priya_patel.pdf",
            "academics": {
                "tenth_percentage": 95.4,
                "twelfth_percentage": 92.8,
                "degree_cgpa": 9.15,
                "degree_name": "B.Tech IT",
                "branch": "Information Technology",
                "year_of_passing": 2026,
            },
        },
        {
            "email": "rahul.mehta@college.edu",
            "password": "Student@123",
            "full_name": "Rahul Mehta",
            "student_id": "CE2022-067",
            "college": "College of Engineering Pune",
            "resume_file": "demo_resume_rahul_mehta.pdf",
            "academics": {
                "tenth_percentage": 93.8,
                "twelfth_percentage": 91.5,
                "degree_cgpa": 8.45,
                "degree_name": "B.E. Computer Engineering",
                "branch": "Computer Engineering",
                "year_of_passing": 2026,
            },
        },
    ]

    student_ids = []
    for s in students:
        uid = register_user(
            email=s["email"],
            password=s["password"],
            full_name=s["full_name"],
            role="student",
            college=s["college"],
            student_id=s["student_id"],
        )
        student_ids.append(uid)

        # Academic record
        conn = get_connection()
        conn.execute(
            """INSERT INTO academic_records
               (student_id, tenth_percentage, twelfth_percentage, degree_cgpa,
                degree_name, branch, year_of_passing)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                uid,
                s["academics"]["tenth_percentage"],
                s["academics"]["twelfth_percentage"],
                s["academics"]["degree_cgpa"],
                s["academics"]["degree_name"],
                s["academics"]["branch"],
                s["academics"]["year_of_passing"],
            ),
        )
        conn.commit()
        conn.close()


    # Create a placement drive
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO placement_drives
           (title, company_name, description, eligibility, deadline, created_by, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "TechCorp Campus Recruitment 2026",
            "TechCorp Solutions",
            "Hiring Software Engineers, SDE Interns and Data Analysts for 2026 batch.",
            "CGPA >= 7.5, no active backlogs",
            "2026-12-15",
            placement_id,
            "open",
        ),
    )
    drive_id = cur.lastrowid

    # Register all students to the drive
    for sid in student_ids:
        conn.execute(
            "INSERT INTO drive_registrations (drive_id, student_id) VALUES (?, ?)",
            (drive_id, sid),
        )
    conn.commit()
    conn.close()

    add_audit_log(placement_id, "SEED_COMPLETED", details="Demo data loaded successfully")

    print("\n" + "=" * 60)
    print("DEMO CREDENTIALS")
    print("=" * 60)
    print("\nPlacement Cell:")
    print("  Email   : placement@college.edu")
    print("  Password: Placement@123")
    print("\nCompany HR (TechCorp):")
    print("  Email   : hr@techcorp.com")
    print("  Password: HR@Tech123")
    print("\nStudents (password for all: Student@123):")
    print("  arjun.sharma@college.edu  (Arjun Sharma)")
    print("  priya.patel@college.edu   (Priya Patel)")
    print("  rahul.mehta@college.edu   (Rahul Mehta)")
    print("\nNo resumes are preloaded. Each student uploads a demo PDF from the demo_resumes folder to start the live browser-encryption workflow.")
    print("=" * 60)


if __name__ == "__main__":
    seed()

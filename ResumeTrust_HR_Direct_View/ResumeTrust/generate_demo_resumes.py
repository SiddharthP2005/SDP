"""
Generate realistic demo PDF resumes for students using reportlab.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "demo_resumes"


def create_resume(filename, data):
    path = OUTPUT_DIR / filename
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Name", fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=4, textColor=colors.HexColor("#1a365d"), fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="Contact", fontSize=9, leading=12, alignment=TA_CENTER, spaceAfter=8, textColor=colors.HexColor("#4a5568")))
    styles.add(ParagraphStyle(name="Section", fontSize=12, leading=15, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#2b6cb0"), fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="Body", fontSize=10, leading=13, spaceAfter=3))
    styles.add(ParagraphStyle(name="ResumeBullet", fontSize=9.5, leading=12, leftIndent=12, spaceAfter=2))

    story = []

    # Header
    story.append(Paragraph(data["name"], styles["Name"]))
    contact = f'{data["email"]}  |  {data["phone"]}  |  {data["location"]}'
    if data.get("linkedin"):
        contact += f'  |  {data["linkedin"]}'
    story.append(Paragraph(contact, styles["Contact"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2b6cb0"), spaceAfter=8))

    # Education
    story.append(Paragraph("EDUCATION", styles["Section"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e0"), spaceAfter=6))

    for edu in data["education"]:
        story.append(Paragraph(f"<b>{edu['degree']}</b> — {edu['institute']}", styles["Body"]))
        story.append(Paragraph(f"{edu['years']}  |  {edu['score']}", styles["ResumeBullet"]))

    # Skills
    story.append(Paragraph("TECHNICAL SKILLS", styles["Section"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e0"), spaceAfter=6))
    story.append(Paragraph(", ".join(data["skills"]), styles["Body"]))

    # Projects
    story.append(Paragraph("PROJECTS", styles["Section"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e0"), spaceAfter=6))
    for proj in data["projects"]:
        story.append(Paragraph(f"<b>{proj['title']}</b>", styles["Body"]))
        story.append(Paragraph(proj["desc"], styles["ResumeBullet"]))
        if proj.get("tech"):
            story.append(Paragraph(f"<i>Tech: {proj['tech']}</i>", styles["ResumeBullet"]))

    # Experience / Internships
    if data.get("experience"):
        story.append(Paragraph("EXPERIENCE / INTERNSHIPS", styles["Section"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e0"), spaceAfter=6))
        for exp in data["experience"]:
            story.append(Paragraph(f"<b>{exp['role']}</b> — {exp['company']} ({exp['duration']})", styles["Body"]))
            story.append(Paragraph(exp["desc"], styles["ResumeBullet"]))

    # Achievements
    if data.get("achievements"):
        story.append(Paragraph("ACHIEVEMENTS", styles["Section"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e0"), spaceAfter=6))
        for ach in data["achievements"]:
            story.append(Paragraph(f"• {ach}", styles["ResumeBullet"]))

    doc.build(story)
    print(f"Generated: {path}")
    return path


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    resumes = [
        {
            "filename": "demo_resume_arjun_sharma.pdf",
            "name": "Arjun Sharma",
            "email": "arjun.sharma@college.edu",
            "phone": "+91 98765 43210",
            "location": "Bengaluru, Karnataka",
            "linkedin": "linkedin.com/in/arjunsharma",
            "education": [
                {"degree": "B.Tech in Computer Science & Engineering", "institute": "National Institute of Technology, Karnataka", "years": "2022 – 2026", "score": "CGPA: 8.72 / 10"},
                {"degree": "Class XII (CBSE)", "institute": "Delhi Public School, Bengaluru", "years": "2021 – 2022", "score": "94.2%"},
                {"degree": "Class X (CBSE)", "institute": "Delhi Public School, Bengaluru", "years": "2019 – 2020", "score": "96.0%"},
            ],
            "skills": ["Python", "Java", "JavaScript", "React", "Node.js", "SQL", "MongoDB", "Git", "Docker", "AWS Basics", "Data Structures & Algorithms"],
            "projects": [
                {"title": "Campus Placement Portal", "desc": "Full-stack web application for managing student placements with role-based access and resume verification.", "tech": "React, Node.js, PostgreSQL"},
                {"title": "Secure File Sharing System", "desc": "Implemented AES-GCM encryption and integrity checks for confidential document exchange.", "tech": "Python, Cryptography, Flask"},
            ],
            "experience": [
                {"role": "Software Engineering Intern", "company": "Infosys Springboard", "duration": "May – Jul 2025", "desc": "Developed REST APIs and improved API response time by 30% using caching."},
            ],
            "achievements": [
                "Winner – Smart India Hackathon (SIH) 2025, Software Edition",
                "Google DSC Lead 2024-25",
                "LeetCode Knight (1900+ rating)",
            ],
        },
        {
            "filename": "demo_resume_priya_patel.pdf",
            "name": "Priya Patel",
            "email": "priya.patel@college.edu",
            "phone": "+91 91234 56789",
            "location": "Ahmedabad, Gujarat",
            "linkedin": "linkedin.com/in/priyapatel",
            "education": [
                {"degree": "B.Tech in Information Technology", "institute": "Nirma University, Ahmedabad", "years": "2022 – 2026", "score": "CGPA: 9.15 / 10"},
                {"degree": "Class XII (GSEB)", "institute": "St. Xavier's High School", "years": "2021 – 2022", "score": "92.8%"},
                {"degree": "Class X (GSEB)", "institute": "St. Xavier's High School", "years": "2019 – 2020", "score": "95.4%"},
            ],
            "skills": ["Python", "C++", "Machine Learning", "TensorFlow", "scikit-learn", "SQL", "Tableau", "Power BI", "Git"],
            "projects": [
                {"title": "ResumeTrust – Secure Placement Platform", "desc": "Built end-to-end encrypted resume sharing system with AES-256-GCM and SHA-256 integrity verification.", "tech": "Python, Cryptography, React"},
                {"title": "Student Performance Predictor", "desc": "ML model predicting academic performance using historical data with 87% accuracy.", "tech": "Python, scikit-learn, Pandas"},
            ],
            "experience": [
                {"role": "Data Science Intern", "company": "TCS iON", "duration": "Jun – Aug 2025", "desc": "Built dashboards and performed exploratory data analysis on placement datasets."},
            ],
            "achievements": [
                "Dean's List – All semesters",
                "1st Prize – National Level Project Exhibition 2025",
                "Published paper in IEEE conference on secure document exchange",
            ],
        },
        {
            "filename": "demo_resume_rahul_mehta.pdf",
            "name": "Rahul Mehta",
            "email": "rahul.mehta@college.edu",
            "phone": "+91 99887 76655",
            "location": "Pune, Maharashtra",
            "linkedin": "linkedin.com/in/rahulmehta",
            "education": [
                {"degree": "B.E. in Computer Engineering", "institute": "College of Engineering Pune (COEP)", "years": "2022 – 2026", "score": "CGPA: 8.45 / 10"},
                {"degree": "Class XII (Maharashtra Board)", "institute": "Fergusson College", "years": "2021 – 2022", "score": "91.5%"},
                {"degree": "Class X (Maharashtra Board)", "institute": "Fergusson College", "years": "2019 – 2020", "score": "93.8%"},
            ],
            "skills": ["Java", "Spring Boot", "React", "MySQL", "Redis", "Kubernetes", "CI/CD", "System Design"],
            "projects": [
                {"title": "Microservices-based E-commerce Backend", "desc": "Designed and implemented order, inventory and payment services with JWT authentication.", "tech": "Spring Boot, Docker, Kafka"},
                {"title": "Real-time Chat Application", "desc": "WebSocket-based chat with end-to-end encryption support.", "tech": "Node.js, Socket.io, React"},
            ],
            "experience": [
                {"role": "Backend Developer Intern", "company": "Persistent Systems", "duration": "May – Jul 2025", "desc": "Worked on microservices and reduced latency of critical APIs."},
            ],
            "achievements": [
                "Finalist – Amazon ML Challenge 2025",
                "Open Source Contributor – Apache projects",
                "Campus Ambassador – GeeksforGeeks",
            ],
        },
    ]

    for r in resumes:
        create_resume(r["filename"], r)

    print("\nAll demo resumes generated successfully.")


if __name__ == "__main__":
    main()

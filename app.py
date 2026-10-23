import os
import uuid
import json
import time
import traceback
import sqlite3
import smtplib
import datetime
import re
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv
from string import Template
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from tools import parse_document, classify_grievance, validate_routing, route_to_department, generate_email_template, transcribe_audio_with_sarvam, extract_field_from_transcript

# Load environment variables
load_dotenv()

# SendGrid Configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "zen7working@gmail.com")

UPLOAD_DIR = "uploads"
EMAIL_SENDER = "grievance-system@demo.local"

os.makedirs(UPLOAD_DIR, exist_ok=True)

EMAIL_HTML_TEMPLATE = Template("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Grievance $grievance_id</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }
        .header { border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }
        .field { margin-bottom: 15px; }
        .label { font-weight: bold; color: #555; display: inline-block; width: 120px; }
        .body-content { background: #f9f9f9; padding: 20px; border-radius: 8px; margin-top: 20px; line-height: 1.6; white-space: pre-wrap; }
        .meta { color: #888; font-size: 12px; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 15px; }
    </style>
</head>
<body>
    <div class="header">
        <h1> Grievance Email Record</h1>
        <p style="color: #666;">Official correspondence record</p>
    </div>
    <div class="field"><span class="label">Grievance ID:</span> $grievance_id</div>
    <div class="field"><span class="label">From:</span> $email_from</div>
    <div class="field"><span class="label">To:</span> $email_to</div>
    <div class="field"><span class="label">Department:</span> $department</div>
    <div class="field"><span class="label">Priority:</span> $priority</div>
    <div class="field"><span class="label">Subject:</span> $email_subject</div>
    <div class="field"><span class="label">Sent At:</span> $email_sent_at</div>
    <div class="body-content">$email_body</div>
    <div class="meta">
        <p>Original Complaint: $complaint_text...</p>
        <p>Submitted: $created_at</p>
    </div>
</body>
</html>""")

@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = sqlite3.connect("grievances.db")
    c = conn.cursor() 
    c.execute("""CREATE TABLE IF NOT EXISTS users
                 (id TEXT PRIMARY KEY, 
                  name TEXT, 
                  phone TEXT, 
                  email TEXT,
                  address TEXT, 
                  pincode TEXT, 
                  govt_id_type TEXT,
                  govt_id_number TEXT,
                  created_at TEXT)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS grievances
                 (id TEXT PRIMARY KEY, user_id TEXT, department TEXT, priority TEXT, summary TEXT,
                  status TEXT, complaint_text TEXT, extracted_text TEXT, file_path TEXT, 
                  created_at TEXT, updated_at TEXT,
                  email_subject TEXT, email_body TEXT, email_to TEXT, 
                  email_from TEXT, email_sent_at TEXT, voice_transcript TEXT,
                  FOREIGN KEY (user_id) REFERENCES users (id))""")

    c.execute("PRAGMA table_info(grievances)")
    columns = [col[1] for col in c.fetchall()]
    new_columns = [
        ("file_path", "TEXT"), ("complaint_text", "TEXT"), ("extracted_text", "TEXT"),
        ("email_subject", "TEXT"), ("email_body", "TEXT"), ("email_to", "TEXT"),
        ("email_from", "TEXT"), ("email_sent_at", "TEXT"), ("voice_transcript", "TEXT"),
        ("updated_at", "TEXT"), ("user_id", "TEXT")
    ]
    for col_name, col_type in new_columns:
        if col_name not in columns:
            c.execute(f"ALTER TABLE grievances ADD COLUMN {col_name} {col_type}")
    c.execute("""CREATE TABLE IF NOT EXISTS department_emails
                 (department TEXT PRIMARY KEY, email TEXT NOT NULL, description TEXT)""")
    default_emails = [
        ("Electric", "zen7working@gmail.com", "Electricity Department"),
        ("Water", "zen7working@gmail.com", "Water Supply Department"),
        ("Gas", "zen7working@gmail.com", "Gas Supply Department"),
        ("Roads", "zen7working@gmail.com", "Roads & Infrastructure"),
        ("Sanitation", "zen7working@gmail.com", "Sanitation Department"),
        ("Healthcare", "zen7working@gmail.com", "Healthcare Department"),
        ("General", "zen7working@gmail.com", "General Administration")
    ]
    for dept, email, desc in default_emails:
        c.execute("INSERT OR IGNORE INTO department_emails (department, email, description) VALUES (?, ?, ?)",
                  (dept, email, desc))
    conn.commit()
    conn.close()
    yield  

app = FastAPI(title="Grievance AI System", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    with open("static/dashboard.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/register-user")
async def register_user(
    name: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    pincode: str = Form(...),
    govt_id_type: str = Form(...),
    govt_id_number: str = Form(...)
):
    try:
        user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
        email = "N/A"
        conn = sqlite3.connect("grievances.db")
        c = conn.cursor()
        c.execute("""INSERT INTO users 
                     (id, name, phone, email, address, pincode, govt_id_type, govt_id_number, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (user_id, name, phone, email, address, pincode, govt_id_type, govt_id_number, 
                   datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return {"user_id": user_id, "name": name, "email": email, "status": "registered"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/voice-register")
async def voice_register(
    audio: UploadFile = File(...),
    language: str = Form("auto"),
    step: int = Form(...),
    collected_data: str = Form("{}")
):
    try:
        audio_bytes = await audio.read()    # Read audio
        print(f" Received audio: {len(audio_bytes)} bytes")
        transcript, detected_language = transcribe_audio_with_sarvam(audio_bytes, language)     # Transcribe with Sarvam
        print(f" Transcript from Sarvam: '{transcript}'")
        if not transcript:
            return JSONResponse(
                status_code=400,
                content={"error": "No speech detected", "transcript": ""}
            )
        fields = ["name", "phone", "address", "pincode", "govt_id_type", "govt_id_number"]      # Get field name for this step
        field_name = fields[step] if step < len(fields) else "unknown"
        print(f" Extracting field: {field_name} from: '{transcript}'")
        extracted_value = extract_field_from_transcript(transcript, field_name)     # Use AI extraction to get clean values
        # Fallback if extraction fails
        if not extracted_value:
            extracted_value = transcript.strip()
        # Clean numeric fields - strip commas, periods, spaces, dashes
        numeric_fields = ["phone", "pincode", "govt_id_number"]
        if field_name in numeric_fields:
            cleaned = re.sub(r'[^0-9]', '', extracted_value)
            if cleaned:
                extracted_value = cleaned
                print(f"Cleaned {field_name}: '{extracted_value}'")
        # Validate phone number (must be exactly 10 digits)
        if field_name == "phone":
            if len(extracted_value) != 10:
                print(f"Phone number '{extracted_value}' is not 10 digits (got {len(extracted_value)})")
                return {
                    "transcript": transcript,
                    "extracted_value": "",
                    "field_name": field_name,
                    "collected_data": json.loads(collected_data) if collected_data else {},
                    "detected_language": detected_language,
                    "status": "success",
                    "validation_error": f"Phone number must be exactly 10 digits. Got {len(extracted_value)} digits. Please try again."
                }
        # Validate pincode (must be exactly 6 digits)
        if field_name == "pincode":
            if len(extracted_value) != 6:
                print(f"Pincode '{extracted_value}' is not 6 digits (got {len(extracted_value)})")
                return {
                    "transcript": transcript,
                    "extracted_value": "",
                    "field_name": field_name,
                    "collected_data": json.loads(collected_data) if collected_data else {},
                    "detected_language": detected_language,
                    "status": "success",
                    "validation_error": f"Pincode must be exactly 6 digits. Got {len(extracted_value)} digits. Please try again."
                }
        # Parse existing collected data
        try:
            data = json.loads(collected_data)
        except:
            data = {}
        # Store the value
        data[field_name] = extracted_value
        print(f"Stored {field_name}: {extracted_value}")
        print(f"Collected data so far: {data}")
        return {
            "transcript": transcript,
            "extracted_value": extracted_value,
            "field_name": field_name,
            "collected_data": data,
            "detected_language": detected_language,
            "status": "success"
        }
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"VOICE REGISTER ERROR:\n{error_detail}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "detail": error_detail}
        )

@app.post("/api/transcribe-audio")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("auto")
):
    try:
        audio_bytes = await audio.read()
        print(f"Received audio: {len(audio_bytes)} bytes")
        print(f"Language setting: {language}")
        transcript, detected_language = transcribe_audio_with_sarvam(audio_bytes, language)
        if transcript:
            return {
                "transcript": transcript,
                "detected_language": detected_language or "auto",
                "status": "success"
            }
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "No speech detected or transcription failed"}
            )
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"TRANSCRIPTION ERROR:\n{error_detail}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "detail": error_detail}
        )

@app.post("/api/generate-template")
async def generate_template(
    user_id: str = Form(...),
    complaint_text: str = Form(...),
    voice_transcript: str = Form(None),
    file: UploadFile = File(None)
):
    try:
        grievance_id = f"GRV-{uuid.uuid4().hex[:8].upper()}"
        combined_input = complaint_text
        if voice_transcript:
            combined_input = f"{voice_transcript}\n\nAdditional details: {complaint_text}"
        extracted = {"raw_text": "[No file uploaded]", "filename": "N/A", "word_count": 0}
        file_path = None
        if file and file.filename:
            safe_name = f"{grievance_id}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, safe_name).replace("\\", "/")
            file_bytes = await file.read()
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            extracted = parse_document(file_bytes, file.filename)
        template = generate_email_template(combined_input, extracted, user_id)
        conn = sqlite3.connect("grievances.db")
        c = conn.cursor()
        c.execute("SELECT email FROM department_emails WHERE department=?", (template["department"],))
        row = c.fetchone()
        dept_email = row[0] if row else f"{template['department'].lower()}-dept@demo.local"
        conn.close()
        return {
            "grievance_id": grievance_id,
            "user_id": user_id,
            "template": template,
            "department_email": dept_email,
            "sender_email": EMAIL_SENDER,
            "extracted_data": extracted,
            "voice_transcript": voice_transcript,
            "file_path": file_path
        }
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"TEMPLATE ERROR:\n{error_detail}")
        return JSONResponse(status_code=500, content={"error": str(e), "detail": error_detail})

@app.post("/api/send-grievance")
async def send_grievance(
    grievance_id: str = Form(...),
    user_id: str = Form(...),
    email_subject: str = Form(...),
    email_body: str = Form(...),
    department: str = Form(...),
    priority: str = Form(...),
    summary: str = Form(...),
    complaint_text: str = Form(...),
    extracted_text: str = Form(None),
    file_path: str = Form(None),
    voice_transcript: str = Form(None),
    email_to: str = Form(...)
):
    try:
        email_sent = send_email(
            to_email=email_to,
            subject=email_subject,
            body=email_body,
            grievance_id=grievance_id
        )
        conn = sqlite3.connect("grievances.db")
        c = conn.cursor()
        now = datetime.datetime.now().isoformat()
        c.execute("""INSERT OR REPLACE INTO grievances 
                     (id, user_id, department, priority, summary, status, complaint_text, 
                      extracted_text, file_path, created_at, updated_at,
                      email_subject, email_body, email_to, email_from, email_sent_at, voice_transcript)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (grievance_id, user_id, department, priority, summary, "submitted",
                   complaint_text, extracted_text or "", file_path, now, now,
                   email_subject, email_body, email_to, EMAIL_SENDER,
                   now if email_sent else None, voice_transcript))
        conn.commit()
        conn.close()
        return {
            "grievance_id": grievance_id,
            "status": "submitted",
            "department": department,
            "priority": priority,
            "email_to": email_to,
            "email_sent": email_sent,
            "submitted_at": now
        }
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"SEND ERROR:\n{error_detail}")
        return JSONResponse(status_code=500, content={"error": str(e), "detail": error_detail})

@app.get("/api/download-email/{grievance_id}")
async def download_email(grievance_id: str):
    conn = sqlite3.connect("grievances.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM grievances WHERE id=?", (grievance_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return JSONResponse(status_code=404, content={"error": "Grievance not found"})
    g = dict(row)
    html_content = EMAIL_HTML_TEMPLATE.substitute(
        grievance_id=g.get('id', 'N/A'),
        email_from=g.get('email_from', EMAIL_SENDER),
        email_to=g.get('email_to', 'N/A'),
        department=g.get('department', 'N/A'),
        priority=g.get('priority', 'N/A'),
        email_subject=g.get('email_subject', 'N/A'),
        email_sent_at=g.get('email_sent_at', 'N/A'),
        email_body=g.get('email_body', 'N/A'),
        complaint_text=(g.get('complaint_text', 'N/A') or '')[:200],
        created_at=g.get('created_at', 'N/A')
    )
    from io import BytesIO
    buffer = BytesIO(html_content.encode('utf-8'))
    return StreamingResponse(
        buffer,
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename=grievance_{grievance_id}.html"}
    )

@app.get("/api/dashboard")
async def get_dashboard(department: str = None):
    conn = sqlite3.connect("grievances.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if department and department != "All":
        c.execute("""SELECT g.id, g.department, g.priority, g.summary, g.status, g.created_at, 
                            g.file_path, g.email_subject, g.email_to, u.name as user_name 
                     FROM grievances g
                     LEFT JOIN users u ON g.user_id = u.id
                     WHERE g.department=? 
                     ORDER BY g.created_at DESC""", (department,))
    else:
        c.execute("""SELECT g.id, g.department, g.priority, g.summary, g.status, g.created_at, 
                            g.file_path, g.email_subject, g.email_to, u.name as user_name 
                     FROM grievances g
                     LEFT JOIN users u ON g.user_id = u.id
                     ORDER BY g.created_at DESC""")
    rows = [dict(row) for row in c.fetchall()]
    c.execute("SELECT department, COUNT(*) as count FROM grievances GROUP BY department")
    stats_rows = [dict(row) for row in c.fetchall()]
    stats = {r["department"]: r["count"] for r in stats_rows}
    total = sum(stats.values())
    conn.close()
    return {"grievances": rows, "stats": stats, "total": total}

@app.get("/api/grievance/{grievance_id}")
async def get_grievance_detail(grievance_id: str):
    conn = sqlite3.connect("grievances.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT g.*, u.name as user_name, u.phone, u.address, u.pincode, u.govt_id_type, u.govt_id_number 
                 FROM grievances g
                 LEFT JOIN users u ON g.user_id = u.id
                 WHERE g.id=?""", (grievance_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    result = dict(row)
    if result.get("file_path"):
        result["file_url"] = "/" + result["file_path"].replace("\\", "/")
    return result

def send_email(to_email, subject, body, grievance_id):
    try:
        if not SENDGRID_API_KEY:
            print("SendGrid API key not configured.")
            return False
        # Create email message
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject=f"[Grievance #{grievance_id}] {subject}",
            html_content=f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: #f0f4f8; padding: 20px; border-radius: 10px; margin-bottom: 20px; border-left: 4px solid #38bdf8;">
                    <h2 style="color: #0f172a; margin: 0;">New Grievance Received</h2>
                    <p style="color: #475569; margin: 5px 0 0 0;">Grievance ID: <strong>#{grievance_id}</strong></p>
                </div>
                <div style="background: white; padding: 20px; border-radius: 10px; border: 1px solid #e2e8f0;">
                    <div style="white-space: pre-wrap; line-height: 1.8;">{body.replace(chr(10), "<br>")}</div>
                </div>
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #e2e8f0;">
                <p style="color: #94a3b8; font-size: 12px; text-align: center;">
                    This is an automated message from the Grievance Management System.
                </p>
            </body>
            </html>
            """,
            plain_text_content=body
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        if response.status_code == 202:
            print(f"Email sent via SendGrid to {to_email}")
            print(f"Subject: [Grievance #{grievance_id}] {subject}")
            return True
        else:
            print(f"SendGrid response: {response.status_code} - {response.body}")
            return False
    except Exception as e:
        print(f"Email send failed: {e}")
        return False

def save_email_to_file(to_email, subject, body, grievance_id):
    try:
        email_file = f"emails/{grievance_id}_email.txt"
        os.makedirs("emails", exist_ok=True)
        with open(email_file, "w", encoding="utf-8") as f:
            f.write(f"To: {to_email}\n")
            f.write(f"From: {SENDGRID_FROM_EMAIL}\n")
            f.write(f"Subject: {subject}\n")
            f.write(f"Grievance ID: {grievance_id}\n")
            f.write("-" * 50 + "\n\n")
            f.write(body)
        print(f"Email saved to file: {email_file}")
        return True
    except Exception as e:
        print(f"Failed to save email: {e}")
        return False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
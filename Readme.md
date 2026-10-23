# AI Grievance System

A FastAPI-based grievance management system that allows users to register complaints, upload documents, record voice complaints, generate AI-powered grievance emails, and track submissions through a department dashboard.

## Features

- Manual user registration
- Voice-based registration
- Text and voice grievance submission
- Audio transcription using Sarvam AI
- Document parsing and OCR
- AI email generation using Gemini
- Automatic department classification
- Priority assignment
- Email delivery through SendGrid
- SQLite database storage
- Department dashboard
- Email record download

## Project Structure

```text
Grievance_local/
├── app.py
├── tools.py
├── README.md
├── requirements.txt
├── .env
├── grievances.db
├── uploads/
├── emails/
└── static/
    ├── index.html
    └── dashboard.html
```

## Technologies Used

- Python
- FastAPI
- SQLite
- Gemini API
- Sarvam AI
- SendGrid
- RapidOCR
- PyMuPDF
- Pillow
- HTML
- CSS
- JavaScript

## Prerequisites

Install the following software:

- Python 3.10 or newer
- Internet connection
- Gemini API key
- Sarvam API key
- SendGrid API key

## Installation

Open PowerShell in the project directory:

```powershell
cd "C:\Users\OASYS-LAP-434\Documents\Grievance_local"
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate the environment again:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Install Dependencies

Create a `requirements.txt` file with:

```text
fastapi
uvicorn[standard]
python-multipart
python-dotenv
requests
sendgrid
PyMuPDF
Pillow
rapidocr-onnxruntime
sarvamai
websockets
```

Install the dependencies:

```powershell
pip install -r requirements.txt
```

## Environment Configuration

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
SARVAM_API_KEY=your_sarvam_api_key
SENDGRID_API_KEY=your_sendgrid_api_key
SENDGRID_FROM_EMAIL=verified_sender@example.com
```

Do not commit `.env` files or API keys to Git.

## Run the Application

Start the application using:

```powershell
python app.py
```

Alternatively:

```powershell
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Open the application:

```text
http://127.0.0.1:8000
```

Open the dashboard:

```text
http://127.0.0.1:8000/dashboard
```

Open the API documentation:

```text
http://127.0.0.1:8000/docs
```

## Application Workflow

### 1. User Registration

Users provide:

- Name
- Phone number
- Address
- Pincode
- Government ID type
- Government ID number

The information is stored in the `users` table.

Users can also register using voice input through the `/api/voice-register` endpoint.

### 2. Complaint Submission

Users can submit complaints by:

- Entering text
- Recording audio
- Uploading a supporting document

Supported file types include:

- PDF
- TXT
- PNG
- JPG/JPEG
- WEBP

### 3. Audio Transcription

Audio complaints are transcribed using Sarvam AI.

Endpoint:

```text
POST /api/transcribe-audio
```

Supported languages include English and several Indian languages.

### 4. Document Processing

The `parse_document()` function in `tools.py` extracts text from uploaded files.

- Text files are read directly.
- PDFs are parsed using PyMuPDF.
- Images are processed using RapidOCR.

### 5. AI Email Generation

The complaint and extracted document text are sent to Gemini AI.

The system generates:

- Email subject
- Email body
- Department
- Priority
- Complaint summary
- Extracted details
- Confidence score

Endpoint:

```text
POST /api/generate-template
```

Supported departments:

- Electric
- Water
- Gas
- Roads
- Sanitation
- Healthcare
- General

### 6. Grievance Submission

After reviewing the generated email, the user submits the grievance.

Endpoint:

```text
POST /api/send-grievance
```

The system:

1. Sends the grievance email through SendGrid.
2. Stores the grievance in SQLite.
3. Assigns a grievance ID.
4. Saves complaint and document details.
5. Displays the submission status.

### 7. Department Dashboard

The dashboard displays:

- Total grievances
- Department statistics
- Complaint summaries
- Priority
- Status
- User information
- Email recipient
- Uploaded files
- Full grievance details

Dashboard URL:

```text
http://127.0.0.1:8000/dashboard
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | User submission page |
| GET | `/dashboard` | Department dashboard |
| POST | `/api/register-user` | Register a user |
| POST | `/api/voice-register` | Register using voice |
| POST | `/api/transcribe-audio` | Transcribe audio |
| POST | `/api/generate-template` | Generate AI email |
| POST | `/api/send-grievance` | Submit grievance |
| GET | `/api/dashboard` | Retrieve dashboard data |
| GET | `/api/grievance/{id}` | Retrieve grievance details |
| GET | `/api/download-email/{id}` | Download email record |

## Database Tables

### Users Table

Stores registered user details:

- `id`
- `name`
- `phone`
- `email`
- `address`
- `pincode`
- `govt_id_type`
- `govt_id_number`
- `created_at`

### Grievances Table

Stores grievance details:

- `id`
- `user_id`
- `department`
- `priority`
- `summary`
- `status`
- `complaint_text`
- `extracted_text`
- `file_path`
- `email_subject`
- `email_body`
- `email_to`
- `email_from`
- `email_sent_at`
- `voice_transcript`

### Department Emails Table

Stores department email mappings:

- `department`
- `email`
- `description`

## Email Configuration

SendGrid is used to deliver grievance emails.

The sender email must be verified in SendGrid:

```env
SENDGRID_FROM_EMAIL=verified_sender@example.com
```

If the SendGrid API key is unavailable, the grievance can still be stored locally, but email delivery will fail.

## Troubleshooting

### Microphone does not work

- Allow microphone permissions in the browser.
- Use `localhost` or HTTPS.
- Check browser security settings.
- Confirm that audio is being uploaded.

### Gemini API fails

- Check `GEMINI_API_KEY`.
- Verify internet connectivity.
- Confirm that the Gemini model is available.
- Check the terminal for API errors.

### Sarvam transcription fails

- Check `SARVAM_API_KEY`.
- Confirm that the Sarvam package is installed.
- Ensure the uploaded audio file is valid.

### SendGrid email fails

- Check `SENDGRID_API_KEY`.
- Verify the sender email address.
- Confirm that the SendGrid account is active.
- Check the terminal output for the response status.

### Uploaded files are not visible

Ensure that the application is started from the project root and that the `uploads` directory exists.


## Stop the Application

Press:

```text
Ctrl + C
```

Deactivate the virtual environment:

```powershell
deactivate
```
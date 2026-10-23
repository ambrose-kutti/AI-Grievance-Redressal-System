import fitz
import io
import json
import requests
import re
import os
import base64
import traceback
import websockets
import asyncio 
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
from dotenv import load_dotenv

load_dotenv()

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

# Sarvam API Configuration
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_URL = "https://api.sarvam.ai/speech-to-text"
try:
    from sarvamai import SarvamAI 
    sarvam_client = SarvamAI(api_subscription_key=SARVAM_API_KEY)
    print("Sarvam client initialized successfully")
except Exception as e:
    print(f" Failed to initialize Sarvam client: {e}")
    sarvam_client = None

ocr_engine = RapidOCR()

def discover_working_model():
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    ]
    print("Discovering working Gemini model...")
    for model in models_to_try:
        try:
            check_url = f"https://generativelanguage.googleapis.com/v1/models/{model}?key={GEMINI_API_KEY}"
            check_response = requests.get(check_url, timeout=5)
            if check_response.status_code == 200:
                print(f"Found working model: {model}")
                return model
            else:
                print(f"Model {model} not available")
        except Exception as e:
            print(f"Error checking {model}: {e}")
            continue
    print("No working Gemini model found")
    return None

def get_gemini_response(prompt, max_retries=2):
    global _working_model
    if not _working_model:
        _working_model = discover_working_model()
    if not _working_model:
        print("No Gemini model available")
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1/models/{_working_model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        headers = {
            "Content-Type": "application/json"
        }
        print(f"Using Gemini model: {_working_model}")
        response = requests.post(url, json=payload, headers=headers, timeout=90)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Gemini error: {response.status_code} - {response.text[:200]}")
            _working_model = None
            return None
    except Exception as e:
        print(f"Gemini error: {e}")
        _working_model = None
        return None
_working_model = None       # Cache for working model

def parse_document(file_bytes, filename):
    text = ""
    filename_lower = filename.lower()
    try:
        if filename_lower.endswith('.pdf'):
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                text += page.get_text()
            doc.close()
        elif filename_lower.endswith('.txt'):
            text = file_bytes.decode('utf-8', errors='ignore')
        elif filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp')):
            image = Image.open(io.BytesIO(file_bytes))
            result, _ = ocr_engine(image)
            if result:
                text = "\\n".join([item[1] for item in result])
            else:
                text = "[No text detected in image]"
        else:
            text = "[Unsupported file type: " + filename + "]"
    except Exception as e:
        text = "[Parse Error: " + str(e) + "]"
    return {
        "raw_text": text[:3000],
        "filename": filename,
        "word_count": len(text.split())
    }

# Sarvam API Configuration - WORKING
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "sk_6n35ryfw_OEpF2Y12rglle4hs7cAcbq8z")
SARVAM_URL = "https://api.sarvam.ai/speech-to-text"

def transcribe_audio_with_sarvam(audio_file_bytes, language_code="auto"):
    if sarvam_client is None:
        print("Sarvam client not initialized")
        return None, None
    try:
        print(f"Transcribing with Sarvam SDK (saaras:v4)")
        print(f"Audio size: {len(audio_file_bytes)} bytes")
        # Language mapping
        language_map = {
            "auto": "en-IN",
            "en-IN": "en-IN",
            "hi-IN": "hi-IN",
            "or-IN": "or-IN",
            "ta-IN": "ta-IN",
            "te-IN": "te-IN",
            "kn-IN": "kn-IN",
            "ml-IN": "ml-IN",
            "bn-IN": "bn-IN",
        }
        lang_code = language_map.get(language_code, "en-IN")
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_file.write(audio_file_bytes)
            tmp_file_path = tmp_file.name
        try:
            with open(tmp_file_path, "rb") as audio_file:
                response = sarvam_client.speech_to_text.transcribe(
                    file=audio_file,
                    model="saaras:v4",
                    language_code=lang_code,
                    mode="transcribe"
                )
            os.unlink(tmp_file_path)    # Clean up temp file
            # Get transcript from response
            transcript = getattr(response, 'transcript', None)
            detected_language = getattr(response, 'language_code', lang_code)
            if transcript:
                print(f"Transcription: {transcript[:100] if transcript else 'No transcript'}...")
                print(f"Detected Language: {detected_language}")
                return transcript, detected_language
            else:
                print("No transcript in response")
                return None, None
        except Exception as e:      # Clean up temp file if it exists
            try:
                os.unlink(tmp_file_path)
            except:
                pass
            raise e
    except Exception as e:
        print(f"Sarvam SDK error: {e}")
        traceback.print_exc()
        return None, None

def transcribe_audio_with_sarvam_rest(audio_file_bytes, lang_code="en-IN"):
    try:
        url = "https://api.sarvam.ai/speech-to-text"
        files = {
            'file': ('audio.wav', audio_file_bytes, 'audio/wav')
        }
        data = {
            'model': 'saaras:v4',
            'language_code': lang_code,
            'mode': 'transcribe',
        }
        headers = {
            'api-key': SARVAM_API_KEY,
        }
        print(f"Sending REST API request...")
        response = requests.post(url, files=files, data=data, headers=headers, timeout=30)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            transcript = result.get('transcript', '')
            detected_language = result.get('language_code', lang_code)
            print(f"REST API Success! Transcript: {transcript[:100]}")
            return transcript, detected_language
        else:
            print(f"REST API Failed: {response.status_code} - {response.text}")
            return None, None
    except Exception as e:
        print(f"REST API error: {e}")
        return None, None

async def transcribe_realtime_sarvam(audio_stream):
    uri = "wss://api.sarvam.ai/speech-to-text/ws"
    headers = {"api-key": SARVAM_API_KEY}
    async with websockets.connect(uri, extra_headers=headers) as websocket:
        # Send audio chunks as they come
        async for chunk in audio_stream:
            await websocket.send(chunk)
            response = await websocket.recv()
            # Process and display real-time transcript
            data = json.loads(response)
            yield data.get('transcript', '')

def get_user_details(user_id):
    import sqlite3
    try:
        conn = sqlite3.connect("grievances.db")
        c = conn.cursor()
        c.execute("SELECT name, phone, address, pincode, govt_id_type, govt_id_number FROM users WHERE id=?", (user_id,))
        user_row = c.fetchone()
        conn.close()
        if user_row:
            return {
                "name": user_row[0],
                "phone": user_row[1],
                "address": user_row[2],
                "pincode": user_row[3],
                "govt_id_type": user_row[4],
                "govt_id_number": user_row[5]
            }
        return None
    except Exception as e:
        print(f"Error fetching user details: {e}")
        return None

def generate_email_template(complaint_text, extracted_data, user_id=None):
    user_info = ""
    user_details = None
    if user_id:
        user_details = get_user_details(user_id)
        if user_details:
            user_info = f"""
                            USER DETAILS:
                            - Name: {user_details['name']}
                            - Phone: {user_details['phone']}
                            - Address: {user_details['address']}
                            - Pincode: {user_details['pincode']}
                            - Govt ID Type: {user_details['govt_id_type']}
                            - Govt ID Number: {user_details['govt_id_number']}
                        """ 
    prompt = f"""You are an Email Template Generator for a Government Grievance System.
                {user_info}
                EXTRACTED DOCUMENT CONTENT:
                {extracted_data['raw_text']}
                USER COMPLAINT/VOICE TRANSCRIPT:
                {complaint_text}
                TASK:
                1. Extract these fields from the input:
                    - sender_name: The person's name (if mentioned in complaint, otherwise use from user details)
                    - contact_info: Phone/email/address (if mentioned)
                    - location: Area/address where issue occurred
                    - issue_type: Brief category of the complaint
                    - department: Which department should handle this? Choose from: Electric, Water, Gas, Roads, Sanitation, Healthcare, General
                    - priority: Low, Medium, High, or Critical
                2. Format a PROFESSIONAL EMAIL with:
                    - Proper greeting (Dear [Department] Team,)
                    - Clear description of the issue
                    - Any relevant details (dates, locations, IDs)
                    - Polite closing with the user's actual name and contact information from the registration
                3. Generate an appropriate subject line
                4. Provide confidence score (0.0 to 1.0)
                IMPORTANT: For the email body, use the actual user details from the registration form. The closing should include:
                    - The user's actual name (not "[Your Name]")
                    - The user's actual phone number (not "[Your Contact Information]")
                    - The user's address if relevant
                OUTPUT STRICT JSON FORMAT:
                {{
                    "subject": "Clear, specific subject line",
                    "body": "Full formatted email body with proper greeting, paragraphs, and closing using actual user details",
                    "extracted": {{
                        "sender_name": "extracted name or from user details",
                        "contact_info": "extracted contact or from user details",
                        "location": "extracted location or from user address",
                        "issue_type": "category of issue"
                    }},
                    "department": "One of: Electric, Water, Gas, Roads, Sanitation, Healthcare, General",
                    "priority": "Low/Medium/High/Critical",
                    "confidence": 0.92,
                    "summary": "One-line summary of the complaint"
                }}
            Respond ONLY with valid JSON."""
    try:
        print("Calling Gemini API")
        response_data = get_gemini_response(prompt, max_retries=3)
        if not response_data:
            raise Exception("All Gemini models failed")
        if "candidates" in response_data and len(response_data["candidates"]) > 0:
            result_raw = response_data["candidates"][0]["content"]["parts"][0]["text"]
            print(f"Gemini Response received (length: {len(result_raw)} characters)")
            result_raw = re.sub(r'```json\s*|\s*```', '', result_raw)
            result = json.loads(result_raw)
        else:
            print("No candidates in Gemini response")
            raise Exception("No response from Gemini API")
        allowed_depts = ["Electric", "Water", "Gas", "Roads", "Sanitation", "Healthcare", "General"]
        dept = result.get("department", "General").strip()
        if dept not in allowed_depts:
            dept = "General"
        priority = result.get("priority", "Medium").strip()
        if priority not in ["Low", "Medium", "High", "Critical"]:
            priority = "Medium"
        extracted = result.get("extracted", {})
        if user_details:
            extracted["sender_name"] = user_details['name']  
            extracted["contact_info"] = f"Phone: {user_details['phone']}, Address: {user_details['address']}"
            extracted["location"] = user_details['address']  
            if not extracted.get("issue_type"):
                extracted["issue_type"] = "General"
        body = result.get("body", complaint_text)
        if user_details:
            body = body.replace("[Your Name]", user_details['name'])
            body = body.replace("[Your Contact Information]", f"Phone: {user_details['phone']}\nAddress: {user_details['address']}")
            body = body.replace("[Your Phone]", user_details['phone'])
            body = body.replace("[Your Address]", user_details['address'])
        return {
            "subject": result.get("subject", "Grievance Submission"),
            "body": body,
            "extracted": extracted,
            "department": dept,
            "priority": priority,
            "confidence": float(result.get("confidence", 0.7)),
            "summary": result.get("summary", "No summary generated"),
            "reasoning": "AI template generated successfully using Gemini",
            "ai_used": True
        }
    except Exception as e:
        print(f" Gemini Error: {e}")
        print(f"Full error: {traceback.format_exc()}")
        text = (complaint_text + " " + extracted_data['raw_text']).lower()
        dept_map = {
            "electric": ["electric", "power", "meter", "voltage", "blackout", "current", "wire", "transformer", "bill"],
            "water":    ["water", "pipe", "leak", "tap", "sewage", "drainage", "flood"],
            "gas":      ["gas", "cylinder", "lpg", "png", "leakage"],
            "roads":    ["road", "pothole", "street", "highway", "bridge", "traffic"],
            "sanitation": ["garbage", "trash", "waste", "cleaning", "toilet", "sewage"],
            "healthcare": ["hospital", "medical", "bill", "surgery", "doctor", "pharmacy", "medicine", "health", "patient", "treatment", "overcharge"]
        }
        scores = {d: sum(1 for kw in kws if kw in text) for d, kws in dept_map.items()}
        best_dept = max(scores, key=scores.get) if max(scores.values()) > 0 else "general"
        user_name = "Your Name"
        user_contact = "Your Contact Information"
        if user_details:
            user_name = user_details['name']
            user_contact = f"Phone: {user_details['phone']}\nAddress: {user_details['address']}"
        basic_body = f"""Dear {best_dept.capitalize()} Department Team,
                        I am writing to bring the following issue to your attention:
                        {complaint_text} 
                        Please look into this matter at the earliest and take necessary action.
                        Thank you for your attention to this matter.
                        Regards,
                        {user_name}
                        {user_contact}"""
        extracted_info = {
            "sender_name": user_details['name'] if user_details else None,
            "contact_info": user_details['phone'] if user_details else None,
            "location": user_details['address'] if user_details else None,
            "issue_type": best_dept
        }
        return {
            "subject": "Grievance regarding " + best_dept.capitalize() + " services",
            "body": basic_body,
            "extracted": extracted_info,
            "department": best_dept.capitalize(),
            "priority": "Medium",
            "confidence": 0.6,
            "summary": complaint_text[:100] + "...",
            "reasoning": f"Fallback mode — Gemini error: {str(e)}",
            "ai_used": False
        }
    
def classify_grievance(complaint_text, extracted_data):
    prompt = f"""You are a Grievance Classification Agent.
                    EXTRACTED DOCUMENT:
                    {extracted_data['raw_text']}
                    USER COMPLAINT:
                    {complaint_text}
                    DEPARTMENTS: Electric, Water, Gas, Roads, Sanitation, Healthcare, General
                    Respond ONLY in this JSON format:
                    {{
                        "department": "Electric",
                        "priority": "High",
                        "summary": "brief summary here",
                        "confidence": 0.95
                    }}"""
    try:
        response_data = get_gemini_response(prompt, max_retries=2)
        if not response_data:
            raise Exception("All Gemini models failed")
        if "candidates" in response_data and len(response_data["candidates"]) > 0:
            result_raw = response_data["candidates"][0]["content"]["parts"][0]["text"]
            result_raw = re.sub(r'```json\s*|\s*```', '', result_raw)
            result = json.loads(result_raw)
        else:
            raise Exception("No response from Gemini API")
        allowed_depts = ["Electric", "Water", "Gas", "Roads", "Sanitation", "Healthcare", "General"]
        dept = result.get("department", "General").strip()
        if dept not in allowed_depts:
            dept = "General"
        return {
            "department": dept,
            "priority": result.get("priority", "Medium"),
            "summary": result.get("summary", "No summary generated"),
            "confidence": float(result.get("confidence", 0.5)),
            "reasoning": "AI classified successfully using Gemini"
        }
    except Exception as e:
        text = (complaint_text + " " + extracted_data['raw_text']).lower()
        dept_map = {
            "electric": ["electric", "power", "meter", "voltage", "blackout", "current", "wire", "transformer", "bill"],
            "water": ["water", "pipe", "leak", "tap", "sewage", "drainage", "flood"],
            "gas": ["gas", "cylinder", "lpg", "png", "leakage"],
            "roads": ["road", "pothole", "street", "highway", "bridge", "traffic"],
            "sanitation": ["garbage", "trash", "waste", "cleaning", "toilet", "sewage"],
            "healthcare": ["hospital", "medical", "bill", "surgery", "doctor", "pharmacy", "medicine", "health", "patient", "treatment", "overcharge"]
        }
        scores = {d: sum(1 for kw in kws if kw in text) for d, kws in dept_map.items()}
        best_dept = max(scores, key=scores.get) if max(scores.values()) > 0 else "general"
        return {
            "department": best_dept.capitalize(),
            "priority": "Medium",
            "summary": "Classified as " + best_dept + " based on keyword matching",
            "confidence": 0.6,
            "reasoning": "Fallback mode — AI service unavailable"
        }

def validate_routing(classification):
    confidence = classification.get("confidence", 0.0)
    is_valid = confidence >= 0.75
    return {
        "is_valid": is_valid,
        "confidence": confidence,
        "action": "route" if is_valid else "escalate_to_human",
        "reason": "Confidence " + str(round(confidence, 2)) + " — " + ("auto-routed" if is_valid else "flagged for review")
    }

def route_to_department(classification, grievance_id, user_id=None, file_path=None, complaint_text=None, extracted_text=None):
    import sqlite3
    import datetime
    try:
        conn = sqlite3.connect("grievances.db")
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS grievances
                     (id TEXT, user_id TEXT, department TEXT, priority TEXT, summary TEXT,
                      status TEXT, complaint_text TEXT, extracted_text TEXT, file_path TEXT, created_at TEXT)""")
        
        c.execute("""INSERT INTO grievances 
                     (id, user_id, department, priority, summary, status, complaint_text, extracted_text, file_path, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (grievance_id, user_id, classification["department"],
                   classification["priority"], classification["summary"],
                   "routed", complaint_text, extracted_text, file_path, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {
        "status": "routed",
        "department": classification["department"],
        "grievance_id": grievance_id
    }

def extract_field_from_transcript(transcript, field_name):
    import re
    field_descriptions = {
        "name": "full name of the person",
        "phone": "10-digit phone number (digits ONLY, absolutely NO commas, dots, hyphens, or spaces)",
        "email": "email address",
        "address": "complete address",
        "pincode": "6-digit pin code (digits ONLY, absolutely NO commas, dots, hyphens, or spaces)",
        "govt_id_type": "government ID type (Aadhar, PAN, Voter ID, Driving License, Passport)",
        "govt_id_number": "government ID number (digits and letters ONLY, no commas or dots)"
    }
    desc = field_descriptions.get(field_name, field_name)
    prompt = f"""You are a data extraction assistant. Extract ONLY the {field_name} from the following text.
                TEXT: "{transcript}"
                FIELD: {field_name}
                DESCRIPTION: {desc}
                Instructions:
                1. Extract ONLY the {field_name} from the text.
                2. If this is phone or pincode or govt_id_number, output ONLY continuous digits/characters with NO commas, NO periods, NO spaces, NO dashes. (Example: 9876543210 not 9,8,7,6,5,4,3,2,1,0).
                3. Return ONLY the extracted value as plain text, no JSON, no explanations.
                4. If not found, return an empty string.
                EXTRACTED VALUE:"""
    try:
        print(f" Extracting {field_name} from transcript...")
        response_data = get_gemini_response(prompt, max_retries=2)
        if not response_data:
            return ""
        if "candidates" in response_data and len(response_data["candidates"]) > 0:
            result_raw = response_data["candidates"][0]["content"]["parts"][0]["text"]
            result = result_raw.strip().strip('"\'')
            if field_name in ["phone", "pincode", "govt_id_number"]:
                result = re.sub(r'[^0-9]', '', result)
            print(f" Extracted {field_name}: {result}")
            return result
        return ""
    except Exception as e:
        print(f"Extraction error for {field_name}: {e}")
        return ""
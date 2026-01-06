from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import io
from pypdf import PdfReader
from docx import Document
import re
from typing import Dict, Any
import json
from weasyprint import HTML
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# AI API Key (add yours)
OPENAI_API_KEY = "your-openai-key-here"  # Get from platform.openai.com

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    target_job: str = Form(""),
    job_requirements: str = Form("")
):
    if not file.filename.lower().endswith(('.pdf', '.docx')):
        raise HTTPException(400, "Only PDF or DOCX allowed")
    
    # Extract text from file
    content = await extract_text(file)
    
    # AI Enhance raw resume
    enhanced_resume = await ai_enhance_resume(content)
    
    # AI Tailor to job
    tailored_resume = await ai_tailor_resume(enhanced_resume, target_job, job_requirements)
    
    # Generate PDF with your sample style
    pdf_bytes = generate_pdf(tailored_resume)
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=enhanced_resume.pdf"}
    )

async def extract_text(file: UploadFile) -> str:
    """Extract text from PDF or DOCX"""
    content = await file.read()
    
    if file.filename.lower().endswith('.pdf'):
        reader = PdfReader(io.BytesIO(content))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    else:  # DOCX
        doc = Document(io.BytesIO(content))
        text = "\n".join([para.text for para in doc.paragraphs])
    
    return text

async def ai_enhance_resume(raw_text: str) -> Dict[str, Any]:
    """AI extracts and enhances raw resume"""
    prompt = f"""
    Extract and enhance this resume. Output JSON with:
    {{
        "name": "Full name",
        "phone": "Phone number",
        "email": "Email",
        "linkedin": "LinkedIn URL",
        "location": "City, State",
        "summary": "Professional summary (3-4 sentences)",
        "skills": {{"Languages": ["Python", "Java"], "ML/DL": ["PyTorch"], "MLOps": ["MLflow"], "Cloud": ["GCP"]}},
        "certifications": ["Cert 1", "Cert 2"],
        "experience": [
            {{
                "title": "Job Title",
                "company": "Company",
                "dates": "Month Year - Month Year", 
                "bullets": ["Achievement 1", "Achievement 2"]
            }}
        ],
        "education": [
            {{"degree": "M.S., Computer Science", "school": "University", "dates": "Month Year"}}
        ]
    }}
    
    Raw resume:
    {raw_text[:4000]}
    """
    
    return await call_openai(prompt)

async def ai_tailor_resume(enhanced: Dict[str, Any], job: str, requirements: str) -> Dict[str, Any]:
    """AI rewrites experience for target job"""
    prompt = f"""
    Tailor this resume for: {job}
    
    Job requirements: {requirements}
    
    Rewrite ONLY the experience bullets to match this job perfectly. Keep other sections same.
    
    Current experience: {json.dumps(enhanced['experience'], indent=2)}
    
    Output SAME JSON structure, but with rewritten bullets.
    """
    
    return await call_openai(prompt)

async def call_openai(prompt: str) -> Dict[str, Any]:
    """Call OpenAI API"""
    import openai
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

def generate_pdf(data: Dict[str, Any]) -> bytes:
    """Generate PDF with YOUR exact sample style"""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ margin: 20px 15px; }}
            body {{ font-family: 'Helvetica', Arial, sans-serif; font-size: 11px; line-height: 1.4; color: #000; }}
            .header {{ text-align: center; margin-bottom: 20px; border-bottom: 3px solid #1a6873; padding-bottom: 10px; }}
            .header h1 {{ font-size: 20px; margin: 0 0 5px 0; color: #1a6873; }}
            .header p {{ font-size: 11px; margin: 0; color: #666; }}
            h2 {{ font-size: 13px; margin: 20px 0 10px 0; border-bottom: 2px solid #000; padding-bottom: 3px; font-weight: 600; }}
            .skills-grid {{ display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 5px; }}
            .skills-label {{ font-weight: 600; }}
            ul {{ margin: 5px 0 10px 15px; padding: 0; }}
            li {{ margin: 3px 0; }}
            .job-entry {{ margin-bottom: 15px; }}
            .job-title {{ font-weight: 600; font-size: 12px; margin-bottom: 2px; }}
            .job-meta {{ font-size: 10px; color: #666; margin-bottom: 5px; }}
            .education-entry {{ margin-bottom: 8px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{{ name }}</h1>
            <p>{{ phone }} | {{ email }} | {{ linkedin }} | {{ location }}</p>
        </div>
        
        <h2>Summary</h2>
        <p>{{ summary }}</p>
        
        <h2>Technical Skills</h2>
        {% for category, items in skills.items() %}
            <div class="skills-grid">
                <div class="skills-label">{{ category }}</div>
                <div>{{ items|join(', ') }}</div>
            </div>
        {% endfor %}
        
        {% if certifications %}
        <h2>Certifications</h2>
        <ul>{% for cert in certifications %}<li>{{ cert }}</li>{% endfor %}</ul>
        {% endif %}
        
        <h2>Professional Experience</h2>
        {% for job in experience %}
        <div class="job-entry">
            <div class="job-title">{{ job.title }}</div>
            <div class="job-meta">{{ job.company }} | {{ job.dates }}</div>
            <ul>{% for bullet in job.bullets %}<li>{{ bullet }}</li>{% endfor %}</ul>
        </div>
        {% endfor %}
        
        <h2>Education</h2>
        {% for edu in education %}
        <div class="education-entry">
            <strong>{{ edu.degree }}</strong><br>
            {{ edu.school }} | {{ edu.dates }}
        </div>
        {% endfor %}
    </body>
    </html>
    """
    
    html = html_template.format(**data)
    return HTML(string=html).write_pdf()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

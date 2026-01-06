from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from weasyprint import HTML as WeasyHTML
import io
import requests
import os

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_URL = "https://api.openai.com/v1/chat/completions"

def call_ai(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a professional resume writer."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4
    }
    resp = requests.post(AI_API_URL, headers=headers, json=data)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return content.strip()

@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

@app.post("/generate")
async def generate_resume(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    location: str = Form(""),
    linkedin: str = Form(""),
    summary_raw: str = Form(""),
    job1_raw: str = Form(""),
    job2_raw: str = Form(""),
    skills_raw: str = Form(""),
    education: str = Form(""),
):
    summary = ""
    if summary_raw.strip():
        summary_prompt = f"""
        Rewrite this resume summary in a professional, concise style (2-3 sentences),
        similar to this sample resume style: short, strong, impact-driven.
        {summary_raw}
        """
        summary = call_ai(summary_prompt)

    job1_bullets = []
    if job1_raw.strip():
        job1_prompt = f"""
        Convert the following responsibilities into 5-7 resume bullet points.
        Use action verbs and results, similar to my sample resume experience section.
        Return only bullets, one per line.
        {job1_raw}
        """
        job1_text = call_ai(job1_prompt)
        job1_bullets = [line.strip("-• ").strip() for line in job1_text.splitlines() if line.strip()]

    job2_bullets = []
    if job2_raw.strip():
        job2_prompt = f"""
        Convert the following responsibilities into 5-7 resume bullet points.
        Use action verbs and results, similar to my sample resume experience section.
        Return only bullets, one per line.
        {job2_raw}
        """
        job2_text = call_ai(job2_prompt)
        job2_bullets = [line.strip("-• ").strip() for line in job2_text.splitlines() if line.strip()]

    skills = ", ".join([s.strip() for s in skills_raw.split(",") if s.strip()])

    context = {
        "request": request,
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": linkedin,
        "summary": summary,
        "skills": skills,
        "education": education,
        "job1_title": "Job Title 1",
        "job1_company": "Company 1",
        "job1_dates": "Dates 1",
        "job1_bullets": job1_bullets,
        "job2_title": "Job Title 2",
        "job2_company": "Company 2",
        "job2_dates": "Dates 2",
        "job2_bullets": job2_bullets,
    }

    html_content = templates.get_template("resume_template.html").render(context)
    pdf_bytes = WeasyHTML(string=html_content).write_pdf()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name or "resume"}.pdf"'},
    )

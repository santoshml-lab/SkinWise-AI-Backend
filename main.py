import os

import requests
from fastapi import FastAPI

app = FastAPI(
    title="SkinWise AI API",
    description="AI-powered skincare analysis platform",
    version="1.0.0",
)

YOUNCAM_API_KEY = os.getenv("YOUNCAM_API_KEY")

YOUNCAM_BASE_URL = "https://yce-api-01.makeupar.com/s2s/v2.1"


@app.get("/")
def root():
    return {
        "status": "success",
        "message": "SkinWise AI backend is running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.get("/youcam-status")
def youcam_status():
    if not YOUNCAM_API_KEY:
        return {
            "status": "error",
            "message": "YouCam API key is not configured.",
        }

    return {
        "status": "success",
        "message": "YouCam API key is configured.",
    }

@app.post("/analyze-skin")
def analyze_skin(image_url: str):
    if not YOUNCAM_API_KEY:
        return {
            "status": "error",
            "message": "YouCam API key is not configured."
        }

    url = f"{YOUNCAM_BASE_URL}/task/skin-analysis"

    headers = {
        "Authorization": f"Bearer {YOUNCAM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "src_file_url": image_url,
        "dst_actions": [
            "acne",
            "moisture",
            "oiliness",
            "pore",
            "texture",
            "redness"
        ],
        "format": "json"
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60
    )

    return response.json()

@app.get("/skin-result/{task_id}")
def skin_result(task_id: str):
    if not YOUNCAM_API_KEY:
        return {
            "status": "error",
            "message": "YouCam API key is not configured."
        }

    url = f"{YOUNCAM_BASE_URL}/task/{task_id}"

    headers = {
        "Authorization": f"Bearer {YOUNCAM_API_KEY}"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=60
    )

    return response.json()

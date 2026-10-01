import os
import httpx
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
from fastapi import Body

app = FastAPI(
    title="SkinWise AI API",
    description="AI Skin Analysis powered by YouCam API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://skin-wise-ai-frontend.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

YOUCAM_API_KEY = os.getenv("YOUCAM_API_KEY")
YOUCAM_API_URL = os.getenv("YOUCAM_API_URL")

FILE_API_URL = "https://yce-api-01.makeupar.com/s2s/v2.0/file"


@app.get("/")
def root():
    return {
        "status": "success",
        "message": "SkinWise AI Backend is running."
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "youcam_key_configured": bool(YOUCAM_API_KEY),
        "youcam_url_configured": bool(YOUCAM_API_URL)
    }


@app.post("/analyze-skin")
async def analyze_skin(file: UploadFile = File(...)):

    if not YOUCAM_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="YOUCAM_API_KEY is not configured."
        )

    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Image file is empty."
        )

    content_type = file.content_type or "image/jpeg"

    headers = {
        "Authorization": f"Bearer {YOUCAM_API_KEY}",
        "Content-Type": "application/json"
    }

    # Step 1: Request upload URL from YouCam File API
    file_payload = {
        "files": [
            {
                "content_type": content_type,
                "file_name": file.filename,
                "file_size": len(image_bytes)
            }
        ]
    }

    async with httpx.AsyncClient(timeout=120) as client:

        file_response = await client.post(
            FILE_API_URL,
            headers=headers,
            json=file_payload
        )

        if file_response.status_code != 200:
            raise HTTPException(
                status_code=file_response.status_code,
                detail=file_response.text
            )

        file_data = file_response.json()

        uploaded_file = file_data["data"]["files"][0]

        file_id = uploaded_file["file_id"]
        upload_request = uploaded_file["requests"][0]

        upload_url = upload_request["url"]
        upload_headers = upload_request.get("headers", {})

        # Step 2: Upload actual image to YouCam's signed URL
        upload_response = await client.put(
            upload_url,
            headers=upload_headers,
            content=image_bytes
        )

        if upload_response.status_code not in [200, 201]:
            raise HTTPException(
                status_code=upload_response.status_code,
                detail="Image upload to YouCam failed."
            )

        # Step 3: Create Skin Analysis task
        task_payload = {
            "src_file_id": file_id,
            "dst_actions": [
                "acne",
                "moisture",
                "oiliness",
                "pore",
                "texture",
                "redness",
                "wrinkle",
                "age_spot",
                "radiance",
                "firmness"
            ],
            "format": "json"
        }

        task_response = await client.post(
            YOUCAM_API_URL,
            headers=headers,
            json=task_payload
        )

        if task_response.status_code != 200:
            raise HTTPException(
                status_code=task_response.status_code,
                detail=task_response.text
            )

        return {
            "status": "success",
            "file_id": file_id,
            "task": task_response.json()
    }

@app.get("/skin-result/{task_id}")
async def skin_result(task_id: str):

    if not YOUCAM_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="YOUCAM_API_KEY is not configured."
        )

    result_url = f"{YOUCAM_API_URL}/{task_id}"

    headers = {
        "Authorization": f"Bearer {YOUCAM_API_KEY}"
    }

    async with httpx.AsyncClient(timeout=120) as client:

        response = await client.get(
            result_url,
            headers=headers
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        return response.json()


@app.post("/personalized-insights")
async def personalized_insights(payload: dict = Body(...)):

    if not GROQ_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not configured."
        )

    scores = payload.get("scores", [])

    if not isinstance(scores, list) or not scores:
        raise HTTPException(
            status_code=400,
            detail="Please provide skin analysis scores."
        )

    prompt = f"""
You are SkinWise AI, a cosmetic skincare guidance assistant.

Analyze these YouCam skin-analysis results:
{json.dumps(scores)}

Return valid JSON with exactly these fields:
{{
  "profile_summary": "A short, balanced summary",
  "focus_areas": ["Up to 3 gentle skincare priorities"],
  "morning_routine": ["Step-by-step general routine"],
  "evening_routine": ["Step-by-step general routine"],
  "product_categories": ["Relevant cosmetic product categories"],
  "note": "A brief safety and uncertainty note"
}}

Important rules:
- These are YouCam UI scores, not acne severity scores.
- Do not assume a high acne score means more acne.
- Interpret scores cautiously and do not invent skin conditions.
- Do not diagnose diseases or promise results.
- Offer gentle, general cosmetic skincare guidance.
- Keep routines simple and suitable for beginners.
- Mention broad-spectrum SPF 30+ sunscreen in the morning routine.
- Do not recommend prescription medicines or harsh treatments.
- If the scores do not establish a concern, say so.
- Return JSON only.
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    request_data = {
        "model": "openai/gpt-oss-20b",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You provide cautious, non-medical cosmetic "
                    "skincare guidance and follow the requested JSON format."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"}
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=request_data
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="AI service request failed. Check backend logs."
            )

        response_data = response.json()
        content = response_data["choices"][0]["message"]["content"]
        insights = json.loads(content)

        return {
            "status": "success",
            "insights": insights
        }

    except HTTPException:
        raise

    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="Could not generate personalized insights."
        )


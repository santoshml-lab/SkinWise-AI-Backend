import os
import httpx
from fastapi import FastAPI, File, UploadFile, HTTPException

app = FastAPI(
    title="SkinWise AI API",
    description="AI Skin Analysis powered by YouCam API",
    version="1.0.0"
)

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

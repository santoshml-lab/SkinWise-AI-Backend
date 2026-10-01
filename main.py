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

Your job is to convert the analysis into simple, cautious,
general cosmetic skincare guidance.

Return valid JSON with exactly these fields:

{{
  "profile_summary": "A short balanced summary",
  "focus_areas": ["Up to 3 general skincare priorities"],
  "morning_routine": ["Simple step-by-step routine"],
  "evening_routine": ["Simple step-by-step routine"],
  "product_categories": ["Approved cosmetic product categories only"],
  "note": "A brief safety and uncertainty note"
}}

IMPORTANT SAFETY AND QUALITY RULES:

1. These are YouCam UI analysis scores.
   Do not treat them as medical measurements or diagnoses.

2. Do not diagnose acne, rosacea, pigmentation disorders,
   skin diseases, or any other medical condition.

3. Do not claim that a high or low score automatically means
   a medical problem.

4. Keep recommendations general and cosmetic.

5. Do not recommend prescription medicines.

6. Do not recommend specific treatment concentrations,
   strong chemical treatments, or aggressive procedures.

7. Do not recommend spot treatments.

8. Do not recommend specific AHA/BHA percentages.

9. Do not recommend retinoids or prescription-strength actives.

10. Do not make claims that a product will cure, remove,
    reverse, or permanently change a skin condition.

11. Keep routines simple and beginner-friendly.

12. Broad-spectrum SPF 30+ sunscreen may be included
    in the morning routine.

13. Only use product categories from this approved list:

    - Gentle cleansers
    - Hydrating toners
    - Lightweight moisturizers
    - Hydrating serums
    - Niacinamide-based cosmetic serums
    - Broad-spectrum SPF 30+ sunscreens
    - Gentle cosmetic exfoliants

14. Do not invent additional product categories.

15. If the analysis does not clearly establish a concern,
    use neutral wording such as "maintain" or "support"
    instead of claiming a problem.

16. Avoid appearance-pressure language such as:
    "perfect skin", "flawless skin", or "fix your skin".

17. Encourage patch-testing new cosmetic products and
    stopping use if irritation occurs.

18. If someone has persistent or concerning skin symptoms,
    suggest consulting a qualified dermatologist.

19. Do not use the skin_age value as a diagnosis or claim
    about the user's actual biological age.

20. Keep profile_summary concise and easy to understand.

21. Keep focus_areas limited to a maximum of 3 items.

22. Keep each routine to approximately 4-5 simple steps.

23. Return JSON only. Do not include Markdown or extra text.
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
                    "You are SkinWise AI. "
                    "Provide cautious, general cosmetic skincare guidance. "
                    "Follow the user's requested JSON structure exactly."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "response_format": {
            "type": "json_object"
        }
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

        content = (
            response_data
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )

        if not content:
            raise HTTPException(
                status_code=502,
                detail="AI returned an empty response."
            )

        insights = json.loads(content)

        required_fields = [
            "profile_summary",
            "focus_areas",
            "morning_routine",
            "evening_routine",
            "product_categories",
            "note"
        ]

        for field in required_fields:
            if field not in insights:
                raise HTTPException(
                    status_code=502,
                    detail=f"AI response is missing field: {field}"
                )

        return {
            "status": "success",
            "insights": insights
        }

    except HTTPException:
        raise

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502,
            detail="AI returned invalid JSON."
        )

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to the AI service."
        )

    except (KeyError, IndexError, TypeError):
        raise HTTPException(
            status_code=502,
            detail="Unexpected response from the AI service."
        )





    


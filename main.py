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

def build_recommendation_context(scores):
    """
    Controlled recommendation layer.

    Important:
    YouCam numeric scores are NOT interpreted as good/bad,
    high/low concern, severity, or diagnosis.
    """

    available_metrics = []

    for item in scores:
        metric_type = item.get("type")

        if metric_type and metric_type not in available_metrics:
            available_metrics.append(metric_type)

    return {
        "measured_metrics": available_metrics,

        "score_interpretation": (
            "Numeric YouCam scores must not be interpreted as "
            "good, bad, high concern, low concern, severity, "
            "or diagnosis."
        ),

        "default_product_categories": [
            "Gentle cleansers",
            "Hydrating toners",
            "Hydrating serums",
            "Lightweight moisturizers",
            "Broad-spectrum SPF 30+ sunscreens"
        ],

        "optional_product_categories": [
            "Niacinamide-based cosmetic serums",
            "Gentle cosmetic exfoliants"
        ],

        "default_focus_areas": [
            "Hydration support",
            "Skin barrier support",
            "Daily sun protection"
        ],

        "recommendation_policy": (
            "Use default product categories for the basic routine. "
            "Do not automatically recommend optional categories "
            "from numeric scores alone."
        )
    }

    
    
        


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
You are SkinWise AI, a cautious cosmetic skincare guidance assistant.

The following data comes from YouCam AI Skin Analysis:

{json.dumps(scores)}

IMPORTANT:
The numeric values in this data are YouCam UI analysis scores.

Do NOT assume that:
- a higher score means a worse skin condition
- a lower score means a better skin condition
- any score represents disease severity
- any score represents medical risk

The score direction and meaning must not be invented.

Your task is to create a simple, balanced cosmetic skincare routine
without diagnosing or labeling a skin problem.

Return valid JSON with exactly these fields:

{{
  "profile_summary": "A short neutral summary",
  "focus_areas": [
    "Up to 3 neutral skincare routine priorities"
  ],
  "morning_routine": [
    "Simple cosmetic skincare steps"
  ],
  "evening_routine": [
    "Simple cosmetic skincare steps"
  ],
  "product_categories": [
    "Approved cosmetic product categories only"
  ],
  "note": "Brief safety and uncertainty note"
}}

SAFETY AND QUALITY RULES:

1. Do not diagnose acne, rosacea, pigmentation disorders,
   skin diseases, or any medical condition.

2. Do not describe any numeric score as a medical measurement.

3. Do not infer that a high or low score means a skin problem.

4. Do not use score magnitude to decide that a person has
   acne, oily skin, wrinkles, pores, redness, pigmentation,
   or any other condition.

5. Do not compare the person's skin with other people.

6. Do not use appearance-pressure language such as:
   "perfect skin", "flawless skin", "fix your skin",
   or similar language.

7. Keep recommendations general and cosmetic.

8. Do not recommend prescription medicines.

9. Do not recommend aggressive procedures.

10. Do not recommend strong chemical treatments.

11. Do not recommend specific AHA/BHA percentages.

12. Do not recommend retinoids or prescription-strength actives.

13. Do not recommend spot treatments.

14. Broad-spectrum SPF 30+ sunscreen may be included.

15. Use only these approved product categories:

    - Gentle cleansers
    - Hydrating toners
    - Hydrating serums
    - Lightweight moisturizers
    - Broad-spectrum SPF 30+ sunscreens

16. Do not invent additional product categories.

17. Product categories must NOT be selected because a numeric
    score is high or low.

18. Focus areas must be neutral routine priorities, not diagnoses
    or claims that the user has a skin problem.

19. Suitable neutral focus areas may include:
    - Daily cleansing
    - Hydration support
    - Moisture support
    - Daily sun protection
    - Simple consistent skincare routine

20. Do not use "skin age" as a diagnosis or as the person's
    biological age.

21. Keep the profile summary concise.

22. Keep focus_areas to a maximum of 3 items.

23. Morning routine should contain approximately 4-5 simple steps.

24. Evening routine should contain approximately 3-4 simple steps.

25. Keep the routine consistent with the approved product categories.

26. Encourage patch-testing new cosmetic products and stopping
    use if irritation occurs.

27. If someone has persistent or concerning skin symptoms,
    suggest consulting a qualified dermatologist.

28. Return JSON only. Do not include Markdown or extra text.

Create a balanced routine based on the available YouCam analysis,
but NEVER invent a concern from the numeric scores.
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
                    "Provide cautious, neutral, general cosmetic skincare guidance. "
                    "Never infer medical conditions or skin concerns from "
                    "numeric UI scores. Follow the requested JSON structure exactly."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
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

        # Keep the AI response aligned with the frontend product catalog.
        allowed_categories = [
            "Gentle cleansers",
            "Hydrating toners",
            "Hydrating serums",
            "Lightweight moisturizers",
            "Broad-spectrum SPF 30+ sunscreens"
        ]

        insights["product_categories"] = [
            category
            for category in insights["product_categories"]
            if category in allowed_categories
        ]

        if not insights["product_categories"]:
            insights["product_categories"] = [
                "Gentle cleansers",
                "Hydrating serums",
                "Lightweight moisturizers",
                "Broad-spectrum SPF 30+ sunscreens"
            ]

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




    
        




    





    


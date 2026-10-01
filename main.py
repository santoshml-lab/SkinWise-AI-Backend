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
            detail="Please provide skin analysis results."
        )

    # ---------------------------------------------------------
    # Extract only the analysis types.
    #
    # IMPORTANT:
    # We intentionally do NOT calculate "high concern" or
    # "low concern" from YouCam UI scores because the UI score
    # direction is not assumed here.
    # ---------------------------------------------------------

    analysis_types = []

    for item in scores:
        if not isinstance(item, dict):
            continue

        metric_type = item.get("type")

        if metric_type and metric_type not in analysis_types:
            analysis_types.append(metric_type)

    # Remove the overall score from the descriptive signal list.
    analysis_types = [
        item for item in analysis_types
        if item != "all"
    ]

    analysis_data = {
        "available_analysis_signals": analysis_types,
        "raw_results": scores
    }

    prompt = f"""
You are SkinWise AI, a cautious cosmetic skincare guidance assistant.

The user has completed a YouCam skin analysis.

Here is the analysis data:

{json.dumps(analysis_data)}

Your job is to convert this information into simple,
balanced and general cosmetic skincare guidance.

IMPORTANT INTERPRETATION RULE:

The numeric values in this dataset are YouCam analysis/UI
scores.

DO NOT assume that:

- a higher score means more concern
- a lower score means more concern
- a higher score means worse skin
- a lower score means better skin

Do not create severity rankings from the numeric scores.

Do not say things such as:

"high acne"

"low moisture"

"high pore visibility"

"severe redness"

"poor skin"

or similar statements unless the source explicitly provides
that interpretation.

Instead, treat the results as analysis signals.

For example:

GOOD:
"The analysis includes measurements related to moisture,
texture and pore appearance."

GOOD:
"Your SkinWise routine can focus on gentle cleansing,
hydration and daily sun protection."

BAD:
"Your high pore score means you have enlarged pores."

BAD:
"Your acne score is very high."

Return valid JSON with exactly these fields:

{{
  "profile_summary": "A short balanced summary",
  "focus_areas": [
    "Up to 3 neutral analysis areas"
  ],
  "morning_routine": [
    "Simple step-by-step cosmetic routine"
  ],
  "evening_routine": [
    "Simple step-by-step cosmetic routine"
  ],
  "product_categories": [
    "Approved cosmetic product categories only"
  ],
  "note": "A brief safety and uncertainty note"
}}

SAFETY AND QUALITY RULES:

1. These results are cosmetic AI skin-analysis signals,
   not medical measurements.

2. Do not diagnose acne, rosacea, pigmentation disorders,
   skin diseases or any other medical condition.

3. Do not claim that a numeric score proves a medical
   problem.

4. Do not infer severity from numeric scores.

5. Keep recommendations general and cosmetic.

6. Do not recommend prescription medicines.

7. Do not recommend aggressive procedures.

8. Do not recommend specific treatment concentrations.

9. Do not recommend specific AHA/BHA percentages.

10. Do not recommend retinoids or prescription-strength
    actives.

11. Do not recommend spot treatments.

12. Do not claim that any product will cure, remove,
    reverse or permanently change a skin condition.

13. Keep routines simple and beginner-friendly.

14. Broad-spectrum SPF 30+ sunscreen may be included in
    the morning routine.

15. Only use product categories from this exact approved list:

    - Gentle cleansers
    - Hydrating toners
    - Lightweight moisturizers
    - Hydrating serums
    - Niacinamide-based cosmetic serums
    - Broad-spectrum SPF 30+ sunscreens
    - Gentle cosmetic exfoliants

16. Do not invent additional product categories.

17. If the analysis does not clearly establish a concern,
    use neutral wording such as "maintain", "support",
    "daily care" or "routine".

18. Do not use appearance-pressure language such as:

    "perfect skin"
    "flawless skin"
    "fix your skin"

19. Encourage patch-testing new cosmetic products.

20. Tell the user to stop using a product if irritation
    occurs.

21. If someone has persistent or concerning skin symptoms,
    suggest consulting a qualified dermatologist.

22. Do not use the skin_age value as a diagnosis or claim
    about the user's biological age.

23. Keep profile_summary concise.

24. Keep focus_areas to a maximum of 3 items.

25. Keep morning_routine to approximately 4-5 steps.

26. Keep evening_routine to approximately 4-5 steps.

27. Product categories should remain broad and cosmetic.

28. Do not mention internal API fields such as ui_score,
    task_id or raw JSON in the user-facing response.

29. Return JSON only.

30. Do not include Markdown or extra text.

IMPORTANT:

The purpose of SkinWise AI is to help users understand their
analysis in a calm and useful way, not to diagnose or judge
their appearance.
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
                    "Provide cautious, general cosmetic skincare "
                    "guidance. Never infer severity from numeric "
                    "YouCam UI scores. Follow the requested JSON "
                    "structure exactly."
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




    





    


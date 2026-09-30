from fastapi import FastAPI

app = FastAPI(
    title="SkinWise AI API",
    description="AI-powered skincare analysis platform",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "status": "success",
        "message": "SkinWise AI backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }

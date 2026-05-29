# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import webhooks, dashboard, privacy_policy

app = FastAPI(
    title="WhatsApp Bill Processing API",
    description="Webhook ingest and OCR processing backend",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
# Notice how we don't apply the webhook signature validation globally.
# It is ONLY applied to the webhook router.
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(privacy_policy.router, prefix="/api/v1/privacy", tags=["Privacy"])

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
"""
v2.7 privacy defaults.
The API processes image bytes in memory and does not persist them here.
Production infrastructure must also disable request-body logging and raw-image tracing.
"""
SENSITIVE_LOG_FIELDS = {"image", "raw_image", "image_bytes", "analysis_text"}

def safe_event(event: str, **meta):
    clean = {k:v for k,v in meta.items() if k not in SENSITIVE_LOG_FIELDS}
    return {"event": event, **clean}

def retention_headers():
    return {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
    }

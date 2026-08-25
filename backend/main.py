import os, json, base64, io
from typing import Literal, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from PIL import Image
from openai import OpenAI

app = FastAPI(title="Senior AI Image Gateway", version="2.9")
origins=[x.strip() for x in os.getenv("ALLOWED_ORIGINS","").split(",") if x.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                       allow_methods=["GET","POST"], allow_headers=["*"])

class PrivacyHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response=await call_next(request)
        response.headers["Cache-Control"]="no-store"
        response.headers["Pragma"]="no-cache"
        response.headers["X-Content-Type-Options"]="nosniff"
        return response

app.add_middleware(PrivacyHeadersMiddleware)
MAX_BYTES=int(os.getenv("MAX_IMAGE_BYTES","12582912"))
DEFAULT_MODEL="gpt-4.1-mini"

class Risk(BaseModel):
    level: Literal["unknown","low","caution","high"]="unknown"
    confidence: float=Field(0,ge=0,le=1)
    reasons: List[str]=Field(default_factory=list,max_length=5)

class Action(BaseModel):
    type: Literal["none","family","official_check","call","map","calendar","retry"]
    label: str
    requires_confirmation: bool=True

class Analysis(BaseModel):
    mode: Literal["safe","explain","screen"]
    summary: str
    important_points: List[str]=Field(default_factory=list,max_length=5)
    risk: Risk
    uncertainty: List[str]=Field(default_factory=list,max_length=5)
    next_actions: List[Action]=Field(default_factory=list,max_length=4)

def safety_gate(x: Analysis):
    blocked=(x.risk.level in {"high","unknown"} or x.risk.confidence < .70)
    return {"analysis":x.model_dump(),
            "safety":{"blocked_from_sensitive_action":blocked,
            "message":"민감한 행동은 중단하고 추가 확인이 필요합니다." if blocked
                      else "민감한 행동은 사용자 확인 후 진행합니다."}}

@app.get("/health")
def health():
    key_configured=bool(os.getenv("OPENAI_API_KEY"))
    model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return {"ok":True,"provider_configured":key_configured,"model":model}

@app.get("/", include_in_schema=False)
def app_home():
    return FileResponse("static/index.html")

@app.post("/api/v1/analyze-image")
async def analyze_image(image: UploadFile=File(...),
                        mode: Literal["safe","explain","screen"]=Form(...),
                        voice_context: str=Form("")):
    raw=await image.read()
    if not raw or len(raw)>MAX_BYTES:
        raise HTTPException(413,"IMAGE_TOO_LARGE")
    try:
        im=Image.open(io.BytesIO(raw)); im.verify()
    except Exception:
        raise HTTPException(415,"UNSUPPORTED_IMAGE")

    key=os.getenv("OPENAI_API_KEY")
    model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if not key:
        raise HTTPException(503,"AI_PROVIDER_NOT_CONFIGURED")

    mime=image.content_type if image.content_type in {"image/jpeg","image/png","image/webp"} else "image/jpeg"
    data=base64.b64encode(raw).decode()
    prompt=f"""You are the analysis engine for a Korean senior-assistance app.
Mode: {mode}. Optional user context: {voice_context}
Return ONLY valid JSON matching exactly these fields:
mode, summary, important_points, risk{{level,confidence,reasons}},
uncertainty, next_actions[{{type,label,requires_confirmation}}].
Allowed next_actions.type values: none, family, official_check, call, map, calendar, retry.
Use Korean. Never claim certainty when evidence is insufficient.
For safe mode, do not declare a message definitely safe merely from an image.
For screen mode, give only the next simple step.
For explain mode, explain: what it is, what matters, what to do next.
Do not use markdown fences around the JSON.
"""
    client=OpenAI(api_key=key)
    try:
        resp=client.responses.create(
            model=model,
            input=[{"role":"user","content":[
                {"type":"input_text","text":prompt},
                {"type":"input_image","image_url":f"data:{mime};base64,{data}"}
            ]}]
        )
        text=(resp.output_text or "").strip()
        if text.startswith("```"):
            lines=text.splitlines()
            if lines and lines[0].startswith("```"): lines=lines[1:]
            if lines and lines[-1].strip()=="```": lines=lines[:-1]
            text="\n".join(lines).strip()
        parsed=Analysis.model_validate(json.loads(text))
        return safety_gate(parsed)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"AI_OUTPUT_ERROR:{type(e).__name__}:{str(e)[:1000]}", flush=True)
        raise HTTPException(502,f"INVALID_AI_OUTPUT:{type(e).__name__}")
    except Exception as e:
        detail=str(e).replace("\n"," ")[:1200]
        print(f"AI_PROVIDER_ERROR:{type(e).__name__}:{detail}", flush=True)
        raise HTTPException(502,f"AI_PROVIDER_ERROR:{type(e).__name__}:{detail}")

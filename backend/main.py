import os, json, base64, io
from typing import Literal, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from PIL import Image
from openai import OpenAI

app = FastAPI(title="Senior AI Image Gateway", version="2.9.1")
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
    type: Literal["none","family","official_check","call","map","calendar","retry"]="none"
    label: str="추가 확인하기"
    requires_confirmation: bool=True

class Analysis(BaseModel):
    mode: Literal["safe","explain","screen"]="safe"
    summary: str="사진을 확인했습니다."
    important_points: List[str]=Field(default_factory=list,max_length=5)
    risk: Risk=Field(default_factory=Risk)
    uncertainty: List[str]=Field(default_factory=list,max_length=5)
    next_actions: List[Action]=Field(default_factory=list,max_length=4)

def _list(v):
    if v is None: return []
    if isinstance(v,list): return [str(x) for x in v if x is not None][:5]
    return [str(v)]

def _level(v):
    s=str(v or "").strip().lower()
    if s in {"unknown","low","caution","high"}: return s
    if any(x in s for x in ["높","위험","high"]): return "high"
    if any(x in s for x in ["주의","경고","확인 필요","caution","medium","moderate"]): return "caution"
    if any(x in s for x in ["낮","안전","low"]): return "low"
    return "unknown"

def normalize(obj, mode):
    if not isinstance(obj,dict): obj={}
    risk=obj.get("risk") if isinstance(obj.get("risk"),dict) else {}
    try: confidence=float(risk.get("confidence",0) or 0)
    except Exception: confidence=0
    confidence=max(0,min(1,confidence))
    actions=[]
    raw_actions=obj.get("next_actions",[])
    if not isinstance(raw_actions,list): raw_actions=[raw_actions]
    allowed={"none","family","official_check","call","map","calendar","retry"}
    for a in raw_actions[:4]:
        if isinstance(a,dict):
            t=str(a.get("type","none")); t=t if t in allowed else "none"
            actions.append({"type":t,"label":str(a.get("label") or "추가 확인하기"),"requires_confirmation":bool(a.get("requires_confirmation",True))})
        elif a:
            actions.append({"type":"none","label":str(a),"requires_confirmation":True})
    clean={
        "mode": mode,
        "summary": str(obj.get("summary") or "사진을 확인했습니다."),
        "important_points": _list(obj.get("important_points")),
        "risk":{"level":_level(risk.get("level")),"confidence":confidence,"reasons":_list(risk.get("reasons"))},
        "uncertainty":_list(obj.get("uncertainty")),
        "next_actions":actions
    }
    return Analysis.model_validate(clean)

def safety_gate(x: Analysis):
    blocked=(x.risk.level in {"high","unknown"} or x.risk.confidence < .70)
    return {"analysis":x.model_dump(),"safety":{"blocked_from_sensitive_action":blocked,
            "message":"민감한 행동은 중단하고 추가 확인이 필요합니다." if blocked else "민감한 행동은 사용자 확인 후 진행합니다."}}

@app.get("/health")
def health():
    key_configured=bool(os.getenv("OPENAI_API_KEY"))
    model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return {"ok":True,"provider_configured":key_configured,"model":model,"version":"2.9.1"}

@app.get("/", include_in_schema=False)
def app_home(): return FileResponse("static/index.html")

@app.post("/api/v1/analyze-image")
async def analyze_image(image: UploadFile=File(...), mode: Literal["safe","explain","screen"]=Form(...), voice_context: str=Form("")):
    raw=await image.read()
    if not raw or len(raw)>MAX_BYTES: raise HTTPException(413,"IMAGE_TOO_LARGE")
    try:
        im=Image.open(io.BytesIO(raw)); im.verify()
    except Exception: raise HTTPException(415,"UNSUPPORTED_IMAGE")
    key=os.getenv("OPENAI_API_KEY")
    model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if not key: raise HTTPException(503,"AI_PROVIDER_NOT_CONFIGURED")
    mime=image.content_type if image.content_type in {"image/jpeg","image/png","image/webp"} else "image/jpeg"
    data=base64.b64encode(raw).decode()
    prompt=f'''You analyze an image for a Korean senior-assistance app. Mode: {mode}. Context: {voice_context}
Return ONLY one JSON object. Use Korean for human-readable text.
Required shape exactly: {{"mode":"{mode}","summary":"...","important_points":["..."],"risk":{{"level":"unknown|low|caution|high","confidence":0.0,"reasons":["..."]}},"uncertainty":["..."],"next_actions":[{{"type":"none|family|official_check|call|map|calendar|retry","label":"...","requires_confirmation":true}}]}}
All important_points, risk.reasons, uncertainty, next_actions MUST be JSON arrays. risk.level MUST be exactly one of unknown, low, caution, high. Do not use markdown. Never claim certainty when evidence is insufficient.'''
    client=OpenAI(api_key=key)
    try:
        resp=client.responses.create(model=model,input=[{"role":"user","content":[{"type":"input_text","text":prompt},{"type":"input_image","image_url":f"data:{mime};base64,{data}"}]}])
        text=(resp.output_text or "").strip()
        if text.startswith("```"):
            lines=text.splitlines(); lines=lines[1:] if lines else lines
            if lines and lines[-1].strip()=="```": lines=lines[:-1]
            text="\n".join(lines).strip()
        obj=json.loads(text)
        return safety_gate(normalize(obj,mode))
    except json.JSONDecodeError as e:
        print(f"AI_OUTPUT_ERROR:JSONDecodeError:{str(e)[:1000]}",flush=True)
        raise HTTPException(502,"INVALID_AI_JSON")
    except Exception as e:
        detail=str(e).replace("\n"," ")[:1200]
        print(f"AI_PROVIDER_ERROR:{type(e).__name__}:{detail}",flush=True)
        raise HTTPException(502,f"AI_PROVIDER_ERROR:{type(e).__name__}:{detail}")

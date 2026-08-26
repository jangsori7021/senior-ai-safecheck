import os, json, base64, io
from typing import Literal, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from PIL import Image
from openai import OpenAI
app=FastAPI(title="Senior AI Life Secretary",version="4.1")
origins=[x.strip() for x in os.getenv("ALLOWED_ORIGINS","").split(",") if x.strip()]
if origins: app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["*"])
class PrivacyHeadersMiddleware(BaseHTTPMiddleware):
 async def dispatch(self,request,call_next):
  response=await call_next(request);response.headers["Cache-Control"]="no-store";response.headers["Pragma"]="no-cache";response.headers["X-Content-Type-Options"]="nosniff";return response
app.add_middleware(PrivacyHeadersMiddleware)
MAX_BYTES=int(os.getenv("MAX_IMAGE_BYTES","12582912"));DEFAULT_MODEL="gpt-4.1-mini"
class Risk(BaseModel):
 level:Literal["unknown","low","caution","high"]="unknown";confidence:float=Field(0,ge=0,le=1);reasons:List[str]=Field(default_factory=list,max_length=5)
class Action(BaseModel):
 type:Literal["none","family","official_check","call","map","calendar","retry"]="none";label:str="추가 확인하기";requires_confirmation:bool=True
class Analysis(BaseModel):
 mode:Literal["safe","explain","screen"]="safe";summary:str="사진을 확인했습니다.";important_points:List[str]=Field(default_factory=list,max_length=5);risk:Risk=Field(default_factory=Risk);uncertainty:List[str]=Field(default_factory=list,max_length=5);next_actions:List[Action]=Field(default_factory=list,max_length=4)
class AskRequest(BaseModel): question:str
def _client():
 key=os.getenv("OPENAI_API_KEY");model=os.getenv("OPENAI_MODEL",DEFAULT_MODEL).strip() or DEFAULT_MODEL
 if not key: raise HTTPException(503,"AI_PROVIDER_NOT_CONFIGURED")
 return OpenAI(api_key=key),model
def _list(v):
 if v is None:return []
 if isinstance(v,list):return [str(x) for x in v if x is not None][:5]
 return [str(v)]
def _level(v):
 s=str(v or "").strip().lower()
 if s in {"unknown","low","caution","high"}:return s
 if any(x in s for x in ["높","위험","high"]):return "high"
 if any(x in s for x in ["주의","경고","확인 필요","caution","medium","moderate"]):return "caution"
 if any(x in s for x in ["낮","안전","low"]):return "low"
 return "unknown"
def normalize(obj,mode):
 if not isinstance(obj,dict):obj={}
 risk=obj.get("risk") if isinstance(obj.get("risk"),dict) else {}
 try:confidence=float(risk.get("confidence",0) or 0)
 except:confidence=0
 confidence=max(0,min(1,confidence));actions=[];raw=obj.get("next_actions",[]);raw=raw if isinstance(raw,list) else [raw];allowed={"none","family","official_check","call","map","calendar","retry"}
 for a in raw[:4]:
  if isinstance(a,dict):
   t=str(a.get("type","none"));actions.append({"type":t if t in allowed else "none","label":str(a.get("label") or "추가 확인하기"),"requires_confirmation":bool(a.get("requires_confirmation",True))})
 return Analysis.model_validate({"mode":mode,"summary":str(obj.get("summary") or "사진을 확인했습니다."),"important_points":_list(obj.get("important_points")),"risk":{"level":_level(risk.get("level")),"confidence":confidence,"reasons":_list(risk.get("reasons"))},"uncertainty":_list(obj.get("uncertainty")),"next_actions":actions})
def safety_gate(x):
 blocked=x.risk.level in {"high","unknown"} or x.risk.confidence<.70
 return {"analysis":x.model_dump(),"safety":{"blocked_from_sensitive_action":blocked,"message":"민감한 행동은 중단하고 추가 확인이 필요합니다." if blocked else "민감한 행동은 사용자 확인 후 진행합니다."}}
@app.get("/health")
def health():return {"ok":True,"provider_configured":bool(os.getenv("OPENAI_API_KEY")),"model":os.getenv("OPENAI_MODEL",DEFAULT_MODEL).strip() or DEFAULT_MODEL,"version":"4.1"}
@app.get("/manifest.json",include_in_schema=False)
def manifest():return FileResponse("static/manifest.json",media_type="application/manifest+json")
@app.get("/icon.svg",include_in_schema=False)
def app_icon():return FileResponse("static/icon.svg",media_type="image/svg+xml")
@app.get("/sw.js",include_in_schema=False)
def service_worker():return FileResponse("static/sw.js",media_type="application/javascript",headers={"Service-Worker-Allowed":"/"})
@app.get("/",include_in_schema=False)
def app_home():
 with open("static/v41.html","r",encoding="utf-8") as f:
  html=f.read().replace("⌨ 글자로 부탁하기","⌨ 글자로 묻기")
  return HTMLResponse(html)
@app.post("/api/v1/ask")
def ask(req:AskRequest):
 q=req.question.strip()
 if not q:raise HTTPException(400,"EMPTY_QUESTION")
 client,model=_client();prompt='''너는 한국 시니어의 AI 생활비서다. 메뉴 사용법을 설명하기보다 사용자가 지금 해결하려는 일을 먼저 파악한다. 반드시 쉬운 한국어 존댓말로 핵심부터 짧게 답한다. 필요하면 지금 할 일을 최대 3단계로 제시한다. 개인 기억과 일정 질문은 앱의 기억비서 기능을 활용하도록 안내한다. 의료·법률·금융은 단정하지 않는다. 사기·송금·비밀번호·인증번호가 관련되면 서두르지 말고 공식기관이나 가족에게 확인하도록 한다. 실시간 정보는 꾸며내지 않는다.'''
 try:
  r=client.responses.create(model=model,input=[{"role":"system","content":[{"type":"input_text","text":prompt}]},{"role":"user","content":[{"type":"input_text","text":q}]}]);return {"answer":r.output_text.strip()}
 except Exception as e:print(f"AI_ASK_ERROR:{type(e).__name__}:{str(e)[:800]}",flush=True);raise HTTPException(502,"AI_ASK_FAILED")
@app.post("/api/v1/analyze-image")
async def analyze_image(image:UploadFile=File(...),mode:Literal["safe","explain","screen"]=Form(...),voice_context:str=Form("")):
 raw=await image.read()
 if not raw or len(raw)>MAX_BYTES:raise HTTPException(413,"IMAGE_TOO_LARGE")
 try:im=Image.open(io.BytesIO(raw));im.verify()
 except:raise HTTPException(415,"UNSUPPORTED_IMAGE")
 client,model=_client();mime=image.content_type if image.content_type in {"image/jpeg","image/png","image/webp"} else "image/jpeg";data=base64.b64encode(raw).decode();prompt=f'''You analyze an image for a Korean senior AI life secretary. Mode: {mode}. Context: {voice_context}\nExplain in very simple Korean: what it is, what the senior should do now, and what to be careful about. Return ONLY JSON: {{"mode":"{mode}","summary":"...","important_points":["..."],"risk":{{"level":"unknown|low|caution|high","confidence":0.0,"reasons":["..."]}},"uncertainty":["..."],"next_actions":[{{"type":"none|family|official_check|call|map|calendar|retry","label":"...","requires_confirmation":true}}]}}. Never claim certainty when evidence is insufficient.'''
 try:
  resp=client.responses.create(model=model,input=[{"role":"user","content":[{"type":"input_text","text":prompt},{"type":"input_image","image_url":f"data:{mime};base64,{data}"}]}]);text=(resp.output_text or "").strip()
  if text.startswith("```"):
   lines=text.splitlines()[1:];lines=lines[:-1] if lines and lines[-1].strip()=="```" else lines;text="\n".join(lines).strip()
  return safety_gate(normalize(json.loads(text),mode))
 except json.JSONDecodeError:raise HTTPException(502,"INVALID_AI_JSON")
 except Exception as e:print(f"AI_PROVIDER_ERROR:{type(e).__name__}:{str(e)[:1000]}",flush=True);raise HTTPException(502,"AI_PROVIDER_ERROR")
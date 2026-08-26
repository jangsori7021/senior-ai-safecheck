import os, json, base64, io
from typing import Literal, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from PIL import Image
from openai import OpenAI

app=FastAPI(title="Senior AI Life Secretary",version="4.5")
origins=[x.strip() for x in os.getenv("ALLOWED_ORIGINS","").split(",") if x.strip()]
if origins: app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["*"])
class PrivacyHeadersMiddleware(BaseHTTPMiddleware):
 async def dispatch(self,request,call_next):
  response=await call_next(request); response.headers["Cache-Control"]="no-store"; response.headers["Pragma"]="no-cache"; response.headers["X-Content-Type-Options"]="nosniff"; return response
app.add_middleware(PrivacyHeadersMiddleware)
MAX_BYTES=int(os.getenv("MAX_IMAGE_BYTES","12582912")); DEFAULT_MODEL="gpt-4.1-mini"
class Risk(BaseModel): level:Literal["unknown","low","caution","high"]="unknown"; confidence:float=Field(0,ge=0,le=1); reasons:List[str]=Field(default_factory=list,max_length=5)
class Action(BaseModel): type:Literal["none","family","official_check","call","map","calendar","retry"]="none"; label:str="추가 확인하기"; requires_confirmation:bool=True
class Analysis(BaseModel): mode:Literal["safe","explain","screen"]="safe"; summary:str="사진을 확인했습니다."; important_points:List[str]=Field(default_factory=list,max_length=5); risk:Risk=Field(default_factory=Risk); uncertainty:List[str]=Field(default_factory=list,max_length=5); next_actions:List[Action]=Field(default_factory=list,max_length=4)
class AskRequest(BaseModel): question:str
def _client():
 key=os.getenv("OPENAI_API_KEY"); model=os.getenv("OPENAI_MODEL",DEFAULT_MODEL).strip() or DEFAULT_MODEL
 if not key: raise HTTPException(503,"AI_PROVIDER_NOT_CONFIGURED")
 return OpenAI(api_key=key),model
def _list(v): return [] if v is None else ([str(x) for x in v if x is not None][:5] if isinstance(v,list) else [str(v)])
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
 confidence=max(0,min(1,confidence)); actions=[]; raw=obj.get("next_actions",[]); raw=raw if isinstance(raw,list) else [raw]; allowed={"none","family","official_check","call","map","calendar","retry"}
 for a in raw[:4]:
  if isinstance(a,dict):
   t=str(a.get("type","none")); actions.append({"type":t if t in allowed else "none","label":str(a.get("label") or "추가 확인하기"),"requires_confirmation":bool(a.get("requires_confirmation",True))})
 return Analysis.model_validate({"mode":mode,"summary":str(obj.get("summary") or "사진을 확인했습니다."),"important_points":_list(obj.get("important_points")),"risk":{"level":_level(risk.get("level")),"confidence":confidence,"reasons":_list(risk.get("reasons"))},"uncertainty":_list(obj.get("uncertainty")),"next_actions":actions})
def safety_gate(x):
 blocked=x.risk.level in {"high","unknown"} or x.risk.confidence<.70
 return {"analysis":x.model_dump(),"safety":{"blocked_from_sensitive_action":blocked,"message":"민감한 행동은 중단하고 추가 확인이 필요합니다." if blocked else "민감한 행동은 사용자 확인 후 진행합니다."}}
@app.get("/health")
def health():return {"ok":True,"provider_configured":bool(os.getenv("OPENAI_API_KEY")),"model":os.getenv("OPENAI_MODEL",DEFAULT_MODEL).strip() or DEFAULT_MODEL,"version":"4.5"}
@app.get("/manifest.json",include_in_schema=False)
def manifest():return FileResponse("static/manifest.json",media_type="application/manifest+json")
@app.get("/icon.svg",include_in_schema=False)
def app_icon():return FileResponse("static/icon.svg",media_type="image/svg+xml")
@app.get("/sw.js",include_in_schema=False)
def service_worker():return FileResponse("static/sw.js",media_type="application/javascript",headers={"Service-Worker-Allowed":"/"})
@app.get("/",include_in_schema=False)
def app_home():
 with open("static/v43.html","r",encoding="utf-8") as f:
  html=f.read()
  html=html.replace("시니어 AI 생활비서 v4.3","시니어 AI 생활비서 v4.5")
  html=html.replace("메뉴를 찾지 마세요. 그냥 말씀하시면 제가 알아서 도와드릴게요.","위에서는 무엇이든 AI에게 말하거나 물어보세요. 아래 카드는 자주 쓰는 기능 바로가기예요.")
  html=html.replace('<div id="recentBox" class="box" hidden></div>','')
  html=html.replace('<button class="card" onclick="showPhotoHistory()"><i>🕘</i><b>최근에 본 것</b><small>전에 확인한 사진과 설명 다시 보기</small></button>','<button class="card" onclick="showPhotoHistory()"><i>🕘</i><b>사진 기록</b><small>전에 확인한 사진과 설명을 다시 봐요</small></button>')
  html=html.replace('<button class="tools" onclick="show(\'tools\')">생활도구 전체보기 〉</button>','<button class="tools" onclick="show(\'tools\')">✨ 생활 한눈에 〉</button>')
  html=html.replace('<div id="historyList"></div></section>','<div id="historyList"></div><div class="two"><button class="btn alt" onclick="goTop()">⬆ 맨 위로</button><button class="btn" onclick="show(\'home\')">⌂ 홈으로</button></div></section>')
  html=html.replace('<div id="memoryList"></div></section>','<div id="memoryList"></div><div class="two"><button class="btn alt" onclick="goTop()">⬆ 맨 위로</button><button class="btn" onclick="show(\'home\')">⌂ 홈으로</button></div></section>')
  html=html.replace('<input id="parkingNote" class="input" placeholder="예: 지하 3층 B구역 27번 기둥"><button class="btn" onclick="parkingPhoto()">📸 주차 위치 사진 찍기</button>','<input id="parkingNote" class="input" placeholder="예: 지하 3층 B구역 27번 기둥"><button class="btn" onclick="voiceToInput(\'parkingNote\')">🎙 주차 위치 말하기</button><button class="btn" onclick="parkingPhoto()">📸 주차 위치 사진 찍기</button>')
  html=html.replace('<textarea id="memoryInput" class="input" rows="4" placeholder="예: 9월 15일 오전 10시 안과"></textarea><button class="btn" onclick="saveMemory()">기억하기</button>','<textarea id="memoryInput" class="input" rows="4" placeholder="예: 9월 15일 오전 10시 안과"></textarea><button class="btn" onclick="voiceToInput(\'memoryInput\')">🎙 말해서 기억하기</button><button class="btn alt" onclick="saveMemory()">⌨ 글자로 기억하기</button>')
  old='<section id="tools" class="screen"><button class="back" onclick="show(\'home\')">⌂ 처음으로</button><h1>생활도구</h1><div class="grid"><button class="card" onclick="naver(\'근처 맛집\')"><i>🍚</i><b>먹을 곳</b><small>근처 식당 찾기</small></button><button class="card" onclick="naver(prompt(\'어디로 갈까요?\')||\'\')"><i>🗺️</i><b>길찾기</b><small>목적지 찾기</small></button><button class="card" onclick="photo(\'safe\')"><i>🚨</i><b>이거 괜찮아?</b><small>수상한 문자·안내문 확인</small></button><button class="card" onclick="show(\'home\')"><i>⌂</i><b>처음으로</b><small>첫 화면으로 이동</small></button></div></section>'
  new='''<section id="tools" class="screen"><button class="back" onclick="show(\'home\')">⌂ 처음으로</button><h1>✨ 생활 한눈에</h1><div class="box notice"><b>마음 편한 생활마당</b><br>밖에 나갈 때도, 집에 있을 때도 필요한 것을 쉽게 찾아보세요.</div><div class="sectionTitle">🚶 밖에 나갈 때</div><div class="grid"><button class="card" onclick="naver(\'근처 맛집\')"><i>🍚</i><b>뭐 먹지?</b><small>가까운 식당 찾아보기</small></button><button class="card" onclick="naver(prompt(\'어디로 갈까요?\')||\'\')"><i>🗺️</i><b>길 찾아줘</b><small>가고 싶은 곳 찾기</small></button><button class="card" onclick="naver(\'근처 화장실\')"><i>🚻</i><b>화장실 어디?</b><small>가까운 화장실 찾기</small></button><button class="card" onclick="naver(\'근처 약국 병원\')"><i>🏥</i><b>병원·약국</b><small>가까운 곳 찾아보기</small></button></div><div class="sectionTitle">🛡️ 건강과 안전</div><div class="grid"><button class="card" onclick="photo(\'safe\')"><i>🚨</i><b>이거 괜찮아?</b><small>수상한 문자·안내문 확인</small></button><button class="card" onclick="show(\'remember\')"><i>💊</i><b>약·병원 기억</b><small>말로 기록해 두기</small></button><button class="card" onclick="show(\'quiet\')"><i>🔕</i><b>조용히 할 시간</b><small>무음 해제도 잊지 않기</small></button><button class="card" onclick="show(\'parking\')"><i>🚗</i><b>내 차 찾기</b><small>주차 위치 다시 보기</small></button></div><div class="sectionTitle">🏠 집에서 편하게</div><div class="grid"><button class="card" onclick="quickAsk(\'계산을 도와줘. 내가 숫자와 계산할 내용을 말할게.\')"><i>🧮</i><b>계산 도와줘</b><small>어려운 계산 쉽게 묻기</small></button><button class="card" onclick="quickAsk(\'휴대폰 사용법을 아주 쉽게 알려줘. 무엇이 어려운지 물어봐 줘.\')"><i>📱</i><b>휴대폰 도움</b><small>사용법을 쉽게 물어보기</small></button><button class="card" onclick="quickAsk(\'오늘 해야 할 일을 정리하고 싶어. 하나씩 물어봐 줘.\')"><i>📝</i><b>오늘 할 일</b><small>하나씩 정리해 보기</small></button><button class="card" onclick="show(\'memory\')"><i>🧠</i><b>내 기억 찾기</b><small>기록해 둔 일 다시 보기</small></button></div><div class="sectionTitle">☕ 마음 편한 시간</div><div class="grid"><button class="card" onclick="quickAsk(\'지금 마음이 편안해질 수 있도록 짧고 따뜻한 이야기를 해줘.\')"><i>☕</i><b>잠깐 쉬어가기</b><small>짧고 편안한 이야기</small></button><button class="card" onclick="quickAsk(\'기분 전환을 하고 싶어. 내 기분에 맞는 간단한 활동을 추천해줘.\')"><i>🌿</i><b>기분 전환</b><small>가볍게 할 일 추천</small></button></div><div class="two"><button class="btn alt" onclick="goTop()">⬆ 맨 위로</button><button class="btn" onclick="show(\'home\')">⌂ 홈으로</button></div></section>'''
  html=html.replace(old,new)
  extra_js="""
function goTop(){try{window.scrollTo(0,0)}catch(e){};try{document.documentElement.scrollTop=0;document.body.scrollTop=0}catch(e){}}
function voiceToInput(targetId){const S=window.SpeechRecognition||window.webkitSpeechRecognition;if(!S){alert('이 휴대폰에서는 음성 입력을 사용할 수 없어요. 글자로 입력해 주세요.');return}let r=new S();r.lang='ko-KR';r.interimResults=false;r.maxAlternatives=1;r.onresult=e=>{let t=e.results[0][0].transcript;let el=$(targetId);el.value=(el.value?el.value+' ':'')+t;el.focus()};r.onerror=()=>alert('잘 듣지 못했어요. 다시 눌러 천천히 말씀해 주세요.');r.start()}
function voiceAsk(){const S=window.SpeechRecognition||window.webkitSpeechRecognition;if(!S){show('asktext');$('askAnswer').hidden=false;$('askAnswer').textContent='이 휴대폰에서는 음성 인식을 사용할 수 없어요. 아래 칸에 글자로 적어주세요.';return}show('asktext');$('askInput').value='';$('askAnswer').hidden=false;$('askAnswer').textContent='🎙 듣고 있어요. 편하게 말씀하세요.';let r=new S();r.lang='ko-KR';r.interimResults=false;r.maxAlternatives=1;r.onresult=e=>{let t=e.results[0][0].transcript;$('askInput').value=t;$('askAnswer').textContent='“'+t+'”라고 들었어요. AI가 답을 준비하고 있어요.';askAI()};r.onerror=()=>{$('askAnswer').textContent='잘 듣지 못했어요. 다시 눌러 말씀하시거나 글자로 적어주세요.'};try{r.start()}catch(e){$('askAnswer').textContent='마이크를 시작하지 못했어요. 잠시 후 다시 눌러주세요.'}}
function quickAsk(q){show('asktext');$('askInput').value=q;askAI()}
"""
  html=html.replace('</script>',extra_js+'</script>'); return HTMLResponse(html)
@app.post("/api/v1/ask")
def ask(req:AskRequest):
 q=req.question.strip()
 if not q:raise HTTPException(400,"EMPTY_QUESTION")
 client,model=_client(); prompt='''너는 한국 시니어의 AI 생활비서다. 사용자가 지금 해결하려는 일을 먼저 파악한다. 쉬운 한국어 존댓말로 결론부터 짧게 답한다. 필요하면 지금 할 일을 최대 3단계로 제시한다. 의료·법률·금융은 단정하지 않는다. 사기·송금·비밀번호·인증번호가 관련되면 행동을 서두르지 말고 공식기관이나 가족에게 확인하도록 한다. 실시간 정보는 꾸며내지 않는다.'''
 try:
  r=client.responses.create(model=model,input=[{"role":"system","content":[{"type":"input_text","text":prompt}]},{"role":"user","content":[{"type":"input_text","text":q}]}]); return {"answer":r.output_text.strip()}
 except Exception as e:
  print(f"AI_ASK_ERROR:{type(e).__name__}:{str(e)[:800]}",flush=True); raise HTTPException(502,"AI_ASK_FAILED")
@app.post("/api/v1/analyze-image")
async def analyze_image(image:UploadFile=File(...),mode:Literal["safe","explain","screen"]=Form(...),voice_context:str=Form("")):
 raw=await image.read()
 if not raw or len(raw)>MAX_BYTES:raise HTTPException(413,"IMAGE_TOO_LARGE")
 try: im=Image.open(io.BytesIO(raw)); im.verify()
 except: raise HTTPException(415,"UNSUPPORTED_IMAGE")
 client,model=_client(); mime=image.content_type if image.content_type in {"image/jpeg","image/png","image/webp"} else "image/jpeg"; data=base64.b64encode(raw).decode(); mode_rule="사기·송금·개인정보·수상한 링크·위험 신호를 우선 확인하고, 위험하면 절대로 누르거나 송금하지 말라고 먼저 말한다." if mode=="safe" else "사진 속 대상이 무엇인지 먼저 식별하고, 시니어가 지금 바로 할 수 있는 행동을 가장 쉽게 설명한다."
 prompt=f'''너는 한국 시니어를 위한 사진 생활비서다. {mode_rule}\n사용자 상황: {voice_context}\n사진을 보고 어려운 전문용어 없이 한국어로 답한다. summary는 반드시 한 문장으로 사진이 무엇인지부터 말한다. important_points는 최대 3개로 지금 하실 일, 조심할 점, 필요할 때 추가 확인 순서로 쓴다. 의료 사진은 단정하지 말고 전문가 확인을 권한다. 잘 안 보이면 추측하지 않는다. Return ONLY JSON: {{"mode":"{mode}","summary":"...","important_points":["..."],"risk":{{"level":"unknown|low|caution|high","confidence":0.0,"reasons":["..."]}},"uncertainty":["..."],"next_actions":[]}}.'''
 try:
  resp=client.responses.create(model=model,input=[{"role":"user","content":[{"type":"input_text","text":prompt},{"type":"input_image","image_url":f"data:{mime};base64,{data}"}]}]); text=(resp.output_text or "").strip()
  if text.startswith("```"):
   lines=text.splitlines()[1:]; lines=lines[:-1] if lines and lines[-1].strip()=="```" else lines; text="\n".join(lines).strip()
  return safety_gate(normalize(json.loads(text),mode))
 except json.JSONDecodeError: raise HTTPException(502,"INVALID_AI_JSON")
 except Exception as e:
  print(f"AI_PROVIDER_ERROR:{type(e).__name__}:{str(e)[:1000]}",flush=True); raise HTTPException(502,"AI_PROVIDER_ERROR")
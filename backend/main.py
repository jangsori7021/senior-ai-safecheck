import os, json, base64, io, re
from typing import Literal, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from PIL import Image
from openai import OpenAI

VERSION="5.2"
app=FastAPI(title="Senior AI Life Secretary",version=VERSION)
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
class MessageRequest(BaseModel): content:str; tone:str="따뜻하고 자연스럽게"
class CookingRequest(BaseModel): ingredients:str; preference:str="쉽고 간단하게"
class DisposalRequest(BaseModel): item:str; region:str=""
class PhoneHelpRequest(BaseModel): task:str; phone_type:str="모르겠어요"; detail:str=""

def _client():
 key=os.getenv("OPENAI_API_KEY"); model=os.getenv("OPENAI_MODEL",DEFAULT_MODEL).strip() or DEFAULT_MODEL
 if not key: raise HTTPException(503,"AI_PROVIDER_NOT_CONFIGURED")
 return OpenAI(api_key=key),model
def _list(v): return [] if v is None else ([str(x) for x in v if x is not None][:5] if isinstance(v,list) else [str(v)])
def _level(v):
 s=str(v or "").strip().lower()
 if s in {"unknown","low","caution","high"}: return s
 if any(x in s for x in ["높","위험","high"]): return "high"
 if any(x in s for x in ["주의","경고","확인 필요","caution","medium","moderate"]): return "caution"
 if any(x in s for x in ["낮","안전","low"]): return "low"
 return "unknown"
def normalize(obj,mode):
 if not isinstance(obj,dict): obj={}
 risk=obj.get("risk") if isinstance(obj.get("risk"),dict) else {}
 try: confidence=float(risk.get("confidence",0) or 0)
 except: confidence=0
 confidence=max(0,min(1,confidence)); actions=[]; raw=obj.get("next_actions",[]); raw=raw if isinstance(raw,list) else [raw]; allowed={"none","family","official_check","call","map","calendar","retry"}
 for a in raw[:4]:
  if isinstance(a,dict):
   t=str(a.get("type","none")); actions.append({"type":t if t in allowed else "none","label":str(a.get("label") or "추가 확인하기"),"requires_confirmation":bool(a.get("requires_confirmation",True))})
 return Analysis.model_validate({"mode":mode,"summary":str(obj.get("summary") or "사진을 확인했습니다."),"important_points":_list(obj.get("important_points")),"risk":{"level":_level(risk.get("level")),"confidence":confidence,"reasons":_list(risk.get("reasons"))},"uncertainty":_list(obj.get("uncertainty")),"next_actions":actions})
def safety_gate(x):
 blocked=x.risk.level in {"high","unknown"} or x.risk.confidence<.70
 return {"analysis":x.model_dump(),"safety":{"blocked_from_sensitive_action":blocked,"message":"민감한 행동은 중단하고 추가 확인이 필요합니다." if blocked else "민감한 행동은 사용자 확인 후 진행합니다."}}

@app.get("/health")
def health(): return {"ok":True,"provider_configured":bool(os.getenv("OPENAI_API_KEY")),"model":os.getenv("OPENAI_MODEL",DEFAULT_MODEL).strip() or DEFAULT_MODEL,"version":VERSION}
@app.get("/manifest.json",include_in_schema=False)
def manifest(): return FileResponse("static/manifest.json",media_type="application/manifest+json")
@app.get("/icon.svg",include_in_schema=False)
def app_icon(): return FileResponse("static/icon.svg",media_type="image/svg+xml")
@app.get("/sw.js",include_in_schema=False)
def service_worker(): return FileResponse("static/sw.js",media_type="application/javascript",headers={"Service-Worker-Allowed":"/"})

@app.get("/",include_in_schema=False)
def app_home():
 with open("static/v43.html","r",encoding="utf-8") as f: html=f.read()
 html=html.replace("시니어 AI 생활비서 v4.3",f"시니어 AI 생활비서 v{VERSION}")
 html=html.replace("메뉴를 찾지 마세요. 그냥 말씀하시면 제가 알아서 도와드릴게요.","위에서는 무엇이든 AI에게 말하거나 물어보세요. 아래 카드는 자주 쓰는 기능 바로가기예요.")
 html=html.replace('<div id="recentBox" class="box" hidden></div>','')
 html=html.replace('<button class="card" onclick="showPhotoHistory()"><i>🕘</i><b>최근에 본 것</b><small>전에 확인한 사진과 설명 다시 보기</small></button>','<button class="card" onclick="showPhotoHistory()"><i>🕘</i><b>사진 기록</b><small>전에 확인한 사진과 설명을 다시 봐요</small></button>')
 html=html.replace('<button class="tools" onclick="show(\'tools\')">생활도구 전체보기 〉</button>','<button class="tools" onclick="show(\'tools\')">✨ 생활 한눈에 〉</button>')
 html=html.replace('<div class="box notice"><b>마음 편한 생활마당</b><br>밖에 나갈 때도, 집에 있을 때도 필요한 것을 쉽게 찾아보세요.</div>','<div class="box notice"><b>필요한 일을 바로 끝내는 생활마당</b><br>겹치는 메뉴는 줄이고, 실제로 자주 쓰는 기능만 모았어요.</div>')
 html=html.replace("openNearby('화장실')","openNearbyFinder('화장실')")
 html=html.replace("openNearby('병원 약국')","openNearbyFinder('병원 약국')")
 html=html.replace("quickAsk('오늘 해야 할 일을 정리하고 싶어. 하나씩 물어봐 줘.')","openTodayTasks()")
 html=html.replace('<button class="card" onclick="openTodayTasks()"><i>📝</i><b>오늘 할 일</b><small>하나씩 정리해 보기</small></button>','<button class="card" onclick="openTodayTasks()"><i>✅</i><b>오늘 할 일</b><small>말로 추가하고 끝낸 일 체크</small></button>')
 html=html.replace('<div id="historyList"></div></section>','<div id="historyList"></div><div class="two"><button class="btn alt" onclick="goTop()">⬆ 맨 위로</button><button class="btn" onclick="show(\'home\')">⌂ 홈으로</button></div></section>')
 html=html.replace('<div id="memoryList"></div></section>','<div id="memoryList"></div><div class="two"><button class="btn alt" onclick="goTop()">⬆ 맨 위로</button><button class="btn" onclick="show(\'home\')">⌂ 홈으로</button></div></section>')
 html=html.replace('<input id="parkingNote" class="input" placeholder="예: 지하 3층 B구역 27번 기둥"><button class="btn" onclick="parkingPhoto()">📸 주차 위치 사진 찍기</button>','<input id="parkingNote" class="input" placeholder="예: 지하 3층 B구역 27번 기둥"><button class="btn" onclick="voiceToInput(\'parkingNote\')">🎙 주차 위치 말하기</button><button class="btn" onclick="parkingPhoto()">📸 주차 위치 사진 찍기</button>')
 html=html.replace('<textarea id="memoryInput" class="input" rows="4" placeholder="예: 9월 15일 오전 10시 안과"></textarea><button class="btn" onclick="saveMemory()">기억하기</button>','<textarea id="memoryInput" class="input" rows="4" placeholder="예: 9월 15일 오전 10시 안과"></textarea><button class="btn" onclick="voiceToInput(\'memoryInput\')">🎙 말해서 기억하기</button><button class="btn alt" onclick="saveMemory()">⌨ 글자로 기억하기</button>')
 tools=re.search(r'<section id="tools".*?</section>',html,re.S)
 if tools:
  block=tools.group(0)
  for label in ["약·병원 기억","조용히 할 시간","내 차 찾기","내 기억 찾기","휴대폰 도움"]:
   block=re.sub(r'<button class="card"[^>]*>.*?<b>'+re.escape(label)+r'</b>.*?</button>','',block,count=1,flags=re.S)
  block=re.sub(r'<div class="sectionTitle">🛡️ 건강과 안전</div><div class="grid">\s*<button class="card"[^>]*>.*?<b>이거 괜찮아\?</b>.*?</button>\s*</div>','',block,count=1,flags=re.S)
  practical='''<div class="sectionTitle">🚶 외출할 때 더 필요한 것</div><div class="grid"><button class="card" onclick="openNearbyFinder('주차장')"><i>🅿️</i><b>주차장 찾기</b><small>현재 위치에서 가까운 주차장 찾기</small></button><button class="card" onclick="openNearbyFinder('은행 ATM')"><i>🏧</i><b>은행·ATM</b><small>현재 위치에서 가까운 ATM 찾기</small></button><button class="card" onclick="openNearbyFinder('주민센터')"><i>🏢</i><b>주민센터</b><small>가까운 행정복지센터 찾기</small></button><button class="card" onclick="openNearbyFinder('우체국')"><i>📮</i><b>우체국</b><small>현재 위치에서 가까운 우체국 찾기</small></button></div><div class="sectionTitle">💡 생활 속 궁금증</div><div class="grid"><button class="card" onclick="openCookingAssistant()"><i>🍳</i><b>뭐 해 먹지?</b><small>재료를 말하면 AI가 요리 추천</small></button><button class="card" onclick="openDisposalAssistant()"><i>♻️</i><b>이거 어떻게 버려?</b><small>물건을 말하면 버리는 법 안내</small></button><button class="card" onclick="openMessageComposer()"><i>💬</i><b>문자 써줘</b><small>말하면 AI가 문자로 완성</small></button><button class="card" onclick="openPhoneHelp()"><i>📱</i><b>휴대폰 알려줘</b><small>하고 싶은 일을 한 단계씩 안내</small></button></div>'''
  marker='<div class="sectionTitle">☕ 마음 편한 시간</div>'
  if marker in block: block=block.replace(marker,practical+marker,1)
  html=html[:tools.start()]+block+html[tools.end():]
 message_section='''<section id="messageComposer" class="screen"><button class="back" onclick="show('tools')">‹ 생활 한눈에</button><h1>💬 문자 써줘</h1><div class="box notice">보내고 싶은 내용을 편하게 말씀하세요. AI가 자연스러운 문자로 다듬어 드려요.</div><textarea id="messageInput" class="input" rows="4" placeholder="예: 김 집사님께 내일 모임에 조금 늦는다고 전해줘"></textarea><button class="btn" onclick="voiceToInput('messageInput')">🎙 말로 내용 입력</button><div class="two"><button class="btn alt" onclick="setTone('짧고 간단하게')">짧게</button><button class="btn alt" onclick="setTone('따뜻하고 자연스럽게')">따뜻하게</button></div><div class="two"><button class="btn alt" onclick="setTone('정중하고 예의 바르게')">정중하게</button><button class="btn alt" onclick="setTone('친근하고 편하게')">친근하게</button></div><div id="messageTone" class="box">말투: 따뜻하고 자연스럽게</div><button class="btn" onclick="composeMessage()">✨ AI가 문자 만들기</button><div id="messageResultWrap" hidden><div class="sectionTitle">완성된 문자</div><textarea id="messageResult" class="input" rows="6"></textarea><button class="btn" onclick="copyMessage()">📋 문자 복사하기</button><button class="btn alt" onclick="sendSMS()">💬 문자 앱 열기</button><button class="btn alt" onclick="composeMessage('더 짧고 간단하게 다시 써줘')">↻ 더 짧게 다시 쓰기</button><button class="btn alt" onclick="composeMessage('조금 더 따뜻하고 부드럽게 다시 써줘')">♡ 더 따뜻하게 고치기</button></div><div class="two"><button class="btn alt" onclick="goTop()">⬆ 맨 위로</button><button class="btn" onclick="show('home')">⌂ 홈으로</button></div></section>'''
 cooking_section='''<section id="cookingAssistant" class="screen"><button class="back" onclick="show('tools')">‹ 생활 한눈에</button><h1>🍳 뭐 해 먹지?</h1><div class="box notice"><b>집에 있는 재료만 말씀하세요.</b><br>어르신이 만들기 쉬운 음식으로 골라서 순서대로 알려드려요.</div><textarea id="cookingInput" class="input" rows="4" placeholder="예: 계란 두 개, 두부, 대파가 있어"></textarea><button class="btn" onclick="voiceToInput('cookingInput')">🎙 재료 말하기</button><div class="two"><button class="btn alt" onclick="setCookingPreference('10분 안에 간단하게')">10분 요리</button><button class="btn alt" onclick="setCookingPreference('재료를 적게 쓰고 아주 쉽게')">아주 쉽게</button></div><div class="two"><button class="btn alt" onclick="setCookingPreference('속이 편하고 자극적이지 않게')">속 편하게</button><button class="btn alt" onclick="setCookingPreference('반찬으로 먹기 좋게')">반찬으로</button></div><div id="cookingPreference" class="box">원하는 방식: 쉽고 간단하게</div><button class="btn" onclick="recommendCooking()">✨ 이 재료로 추천해줘</button><div id="cookingResultWrap" hidden><div class="sectionTitle">추천 요리</div><div id="cookingResult" class="box"></div><button class="btn alt" onclick="recommendCooking('다른 음식 하나를 추천해줘')">↻ 다른 음식 추천</button><button class="btn alt" onclick="recommendCooking('조리 순서를 더 짧고 쉽게 다시 설명해줘')">👵 더 쉽게 설명</button></div><div class="two"><button class="btn alt" onclick="goTop()">⬆ 맨 위로</button><button class="btn" onclick="show('home')">⌂ 홈으로</button></div></section>'''
 disposal_section='''<section id="disposalAssistant" class="screen"><button class="back" onclick="show('tools')">‹ 생활 한눈에</button><h1>♻️ 이거 어떻게 버려?</h1><div class="box notice"><b>버릴 물건을 말씀하세요.</b><br>재활용인지, 일반쓰레기인지, 따로 버려야 하는지 쉽게 알려드려요.</div><textarea id="disposalInput" class="input" rows="3" placeholder="예: 깨진 유리컵, 스티로폼 상자, 오래된 프라이팬"></textarea><button class="btn" onclick="voiceToInput('disposalInput')">🎙 물건 이름 말하기</button><input id="disposalRegion" class="input" placeholder="지역(선택) 예: 대구 북구"><button class="btn alt" onclick="voiceToInput('disposalRegion')">🎙 지역 말하기</button><button class="btn" onclick="checkDisposal()">✨ 버리는 방법 알려줘</button><div id="disposalResultWrap" hidden><div class="sectionTitle">버리는 방법</div><div id="disposalResult" class="box"></div><button class="btn alt" onclick="checkDisposal('더 짧고 쉽게, 핵심만 다시 설명해줘')">👵 더 쉽게 설명</button><button class="btn alt" onclick="checkDisposal('이 물건이 재활용 가능한지와 주의할 점을 다시 확인해줘')">🔎 다시 확인</button></div><div class="box notice"><b>지역마다 규칙이 조금 다를 수 있어요.</b><br>AI가 확실하지 않으면 주민센터나 구청 확인이 필요하다고 안내합니다.</div><div class="two"><button class="btn alt" onclick="goTop()">⬆ 맨 위로</button><button class="btn" onclick="show('home')">⌂ 홈으로</button></div></section>'''
 phone_section='''<section id="phoneHelp" class="screen"><button class="back" onclick="show('tools')">‹ 생활 한눈에</button><h1>📱 휴대폰 알려줘</h1><div class="box notice"><b>하고 싶은 일을 말씀하세요.</b><br>한꺼번에 어렵게 설명하지 않고, 한 단계씩 알려드려요.</div><textarea id="phoneTask" class="input" rows="3" placeholder="예: 사진을 딸에게 보내고 싶어요 / 글씨를 크게 하고 싶어요"></textarea><button class="btn" onclick="voiceToInput('phoneTask')">🎙 하고 싶은 일 말하기</button><div class="sectionTitle">휴대폰 종류</div><div class="two"><button class="btn alt" onclick="setPhoneType('갤럭시 안드로이드')">갤럭시</button><button class="btn alt" onclick="setPhoneType('아이폰')">아이폰</button></div><button class="btn alt" onclick="setPhoneType('모르겠어요')">휴대폰 종류를 모르겠어요</button><div id="phoneTypeBox" class="box">휴대폰: 모르겠어요</div><textarea id="phoneDetail" class="input" rows="2" placeholder="지금 화면에 보이는 글이나 버튼을 적어도 좋아요 (선택)"></textarea><button class="btn" onclick="askPhoneHelp()">✨ 한 단계씩 알려줘</button><div id="phoneResultWrap" hidden><div class="sectionTitle">지금 하실 일</div><div id="phoneResult" class="box"></div><div class="two"><button class="btn alt" onclick="phoneNext('다음 단계만 알려줘')">다음 단계</button><button class="btn alt" onclick="phoneNext('방금 설명을 더 쉽게 다시 말해줘')">더 쉽게</button></div><button class="btn alt" onclick="phoneNext('잘못 눌렀을 때 원래 화면으로 돌아가는 방법도 알려줘')">↩ 잘못 눌렀어요</button></div><div class="box notice">휴대폰 화면이 설명과 다르면, 보이는 글자를 그대로 적어 주세요. AI가 그 화면을 기준으로 다시 안내합니다.</div><div class="two"><button class="btn alt" onclick="goTop()">⬆ 맨 위로</button><button class="btn" onclick="show('home')">⌂ 홈으로</button></div></section>'''
 nearby_section='''<section id="nearbyFinder" class="screen"><button class="back" onclick="show('tools')">‹ 생활 한눈에</button><h1>📍 가까운 곳 찾기</h1><div id="nearbyTitle" class="box notice"><b>현재 위치에서 가까운 곳을 찾아드려요.</b></div><div id="nearbyStatus" class="box">아래 버튼을 누르면 휴대폰의 현재 위치를 사용합니다.</div><button class="btn" onclick="findNearbyNow()">📍 내 위치로 바로 찾기</button><div class="box notice">위치 권한을 허용하면 지도 앱에서 현재 위치 주변을 바로 검색합니다. 위치를 허용하지 않아도 지역 이름을 직접 적을 수 있어요.</div><input id="nearbyArea" class="input" placeholder="예: 대구 북구 연경동"><button class="btn alt" onclick="voiceToInput('nearbyArea')">🎙 지역 말하기</button><button class="btn alt" onclick="findNearbyByArea()">🔎 이 지역에서 찾기</button><div class="two"><button class="btn alt" onclick="goTop()">⬆ 맨 위로</button><button class="btn" onclick="show('home')">⌂ 홈으로</button></div></section>'''
 today_section='''<section id="todayTasks" class="screen"><button class="back" onclick="show('tools')">‹ 생활 한눈에</button><h1>✅ 오늘 할 일</h1><div class="box notice"><b>오늘 해야 할 일을 하나씩 적어두세요.</b><br>말로 추가하고, 끝난 일은 크게 체크할 수 있어요.</div><input id="todayTaskInput" class="input" placeholder="예: 오후 3시 약국 가기"><button class="btn" onclick="voiceToInput('todayTaskInput')">🎙 할 일 말하기</button><button class="btn alt" onclick="addTodayTask()">＋ 오늘 할 일 추가</button><div id="todayTaskList"></div><button class="btn alt" onclick="clearDoneTasks()">✓ 끝난 일 정리하기</button><div class="two"><button class="btn alt" onclick="goTop()">⬆ 맨 위로</button><button class="btn" onclick="show('home')">⌂ 홈으로</button></div></section>'''
 html=html.replace('<section id="travel"',message_section+cooking_section+disposal_section+phone_section+nearby_section+today_section+'<section id="travel"',1)
 extra_js="""
let messageTone='따뜻하고 자연스럽게';let cookingPreference='쉽고 간단하게';let phoneType='모르겠어요';let lastPhoneAnswer='';let nearbyKind='주차장';
function goTop(){try{window.scrollTo(0,0)}catch(e){};try{document.documentElement.scrollTop=0;document.body.scrollTop=0}catch(e){}}
function voiceToInput(targetId){const S=window.SpeechRecognition||window.webkitSpeechRecognition;if(!S){alert('이 휴대폰에서는 음성 입력을 사용할 수 없어요. 글자로 입력해 주세요.');return}let r=new S();r.lang='ko-KR';r.interimResults=false;r.maxAlternatives=1;r.onresult=e=>{let t=e.results[0][0].transcript;let el=$(targetId);el.value=(el.value?el.value+' ':'')+t;el.focus()};r.onerror=()=>alert('잘 듣지 못했어요. 다시 눌러 천천히 말씀해 주세요.');r.start()}
function voiceAsk(){const S=window.SpeechRecognition||window.webkitSpeechRecognition;if(!S){show('asktext');$('askAnswer').hidden=false;$('askAnswer').textContent='이 휴대폰에서는 음성 인식을 사용할 수 없어요. 아래 칸에 글자로 적어주세요.';return}show('asktext');$('askInput').value='';$('askAnswer').hidden=false;$('askAnswer').textContent='🎙 듣고 있어요. 편하게 말씀하세요.';let r=new S();r.lang='ko-KR';r.interimResults=false;r.maxAlternatives=1;r.onresult=e=>{let t=e.results[0][0].transcript;$('askInput').value=t;$('askAnswer').textContent='“'+t+'”라고 들었어요. AI가 답을 준비하고 있어요.';askAI()};r.onerror=()=>{$('askAnswer').textContent='잘 듣지 못했어요. 다시 눌러 말씀하시거나 글자로 적어주세요.'};try{r.start()}catch(e){$('askAnswer').textContent='마이크를 시작하지 못했어요. 잠시 후 다시 눌러주세요.'}}
function quickAsk(q){show('asktext');$('askInput').value=q;askAI()}
function openMessageComposer(){show('messageComposer');$('messageResultWrap').hidden=true;goTop()}
function setTone(t){messageTone=t;$('messageTone').textContent='말투: '+t}
async function composeMessage(revise=''){let content=$('messageInput').value.trim();if(revise&&$('messageResult').value.trim())content='현재 문장: '+$('messageResult').value.trim()+'\n수정 요청: '+revise;if(!content){alert('보내고 싶은 내용을 말하거나 적어주세요.');return}$('messageResultWrap').hidden=false;$('messageResult').value='AI가 문자를 만들고 있어요...';try{let r=await fetch('/api/v1/compose-message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:content,tone:messageTone})});if(!r.ok)throw new Error();let d=await r.json();$('messageResult').value=d.message||'문자를 만들지 못했어요.'}catch(e){$('messageResult').value='지금은 AI 연결이 원활하지 않아요. 잠시 후 다시 눌러주세요.'}}
async function copyMessage(){let t=$('messageResult').value.trim();if(!t)return;try{await navigator.clipboard.writeText(t);alert('문자를 복사했어요. 문자나 카톡에 붙여넣으세요.')}catch(e){$('messageResult').select();document.execCommand('copy');alert('문자를 복사했어요.')}}
function sendSMS(){let t=$('messageResult').value.trim();if(!t){alert('먼저 문자를 만들어 주세요.');return}location.href='sms:?&body='+encodeURIComponent(t)}
function openCookingAssistant(){show('cookingAssistant');$('cookingResultWrap').hidden=true;goTop()}
function setCookingPreference(t){cookingPreference=t;$('cookingPreference').textContent='원하는 방식: '+t}
async function recommendCooking(extra=''){let ingredients=$('cookingInput').value.trim();if(!ingredients){alert('집에 있는 재료를 말하거나 적어주세요.');return}let preference=cookingPreference+(extra?' / '+extra:'');$('cookingResultWrap').hidden=false;$('cookingResult').textContent='AI가 만들기 쉬운 음식을 찾고 있어요...';try{let r=await fetch('/api/v1/cooking',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ingredients:ingredients,preference:preference})});if(!r.ok)throw new Error();let d=await r.json();$('cookingResult').textContent=d.answer||'추천을 만들지 못했어요.'}catch(e){$('cookingResult').textContent='지금은 AI 연결이 원활하지 않아요. 잠시 후 다시 눌러주세요.'}}
function openDisposalAssistant(){show('disposalAssistant');$('disposalResultWrap').hidden=true;goTop()}
async function checkDisposal(extra=''){let item=$('disposalInput').value.trim(),region=$('disposalRegion').value.trim();if(!item){alert('버릴 물건을 말하거나 적어주세요.');return}if(extra)item=item+' / 추가 요청: '+extra;$('disposalResultWrap').hidden=false;$('disposalResult').textContent='AI가 버리는 방법을 확인하고 있어요...';try{let r=await fetch('/api/v1/disposal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item:item,region:region})});if(!r.ok)throw new Error();let d=await r.json();$('disposalResult').textContent=d.answer||'방법을 확인하지 못했어요.'}catch(e){$('disposalResult').textContent='지금은 AI 연결이 원활하지 않아요. 잠시 후 다시 눌러주세요.'}}
function openPhoneHelp(){show('phoneHelp');$('phoneResultWrap').hidden=true;lastPhoneAnswer='';goTop()}
function setPhoneType(t){phoneType=t;$('phoneTypeBox').textContent='휴대폰: '+t}
async function askPhoneHelp(extra=''){let task=$('phoneTask').value.trim(),detail=$('phoneDetail').value.trim();if(!task){alert('휴대폰으로 하고 싶은 일을 말하거나 적어주세요.');return}if(extra)detail=(detail?detail+' / ':'')+extra+(lastPhoneAnswer?' / 이전 안내: '+lastPhoneAnswer:'');$('phoneResultWrap').hidden=false;$('phoneResult').textContent='AI가 지금 화면에서 할 일을 찾고 있어요...';try{let r=await fetch('/api/v1/phone-help',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:task,phone_type:phoneType,detail:detail})});if(!r.ok)throw new Error();let d=await r.json();lastPhoneAnswer=d.answer||'';$('phoneResult').textContent=lastPhoneAnswer||'안내를 만들지 못했어요.'}catch(e){$('phoneResult').textContent='지금은 AI 연결이 원활하지 않아요. 잠시 후 다시 눌러주세요.'}}
function phoneNext(x){askPhoneHelp(x)}
function openNearbyFinder(kind){nearbyKind=kind;show('nearbyFinder');$('nearbyTitle').innerHTML='<b>📍 '+kind+' 찾기</b><br>현재 위치에서 가까운 곳을 지도에서 찾아드려요.';$('nearbyStatus').textContent='아래 버튼을 누르면 휴대폰의 현재 위치를 사용합니다.';goTop()}
function mapsUrl(q){return 'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(q)}
function findNearbyNow(){if(!navigator.geolocation){$('nearbyStatus').textContent='이 휴대폰에서는 현재 위치를 사용할 수 없어요. 아래에 지역 이름을 적어주세요.';return}$('nearbyStatus').textContent='현재 위치를 확인하고 있어요...';navigator.geolocation.getCurrentPosition(p=>{let q=nearbyKind+' near '+p.coords.latitude+','+p.coords.longitude;$('nearbyStatus').textContent='지도를 열어 가까운 '+nearbyKind+'을 찾습니다.';window.location.href=mapsUrl(q)},e=>{$('nearbyStatus').textContent='위치 권한을 사용할 수 없어요. 아래에 동네 이름을 말하거나 적어주세요.'},{enableHighAccuracy:true,timeout:10000,maximumAge:60000})}
function findNearbyByArea(){let a=$('nearbyArea').value.trim();if(!a){alert('찾을 지역을 말하거나 적어주세요.');return}window.location.href=mapsUrl(a+' '+nearbyKind)}
function todayTasks(){try{return JSON.parse(localStorage.getItem('senior_today_tasks_v1')||'[]')}catch(e){return []}}
function saveTodayTasks(a){localStorage.setItem('senior_today_tasks_v1',JSON.stringify(a.slice(0,50)))}
function openTodayTasks(){show('todayTasks');renderTodayTasks();goTop()}
function addTodayTask(){let el=$('todayTaskInput'),text=el.value.trim();if(!text){alert('오늘 할 일을 말하거나 적어주세요.');return}let a=todayTasks();a.unshift({id:Date.now(),text:text,done:false,time:Date.now()});saveTodayTasks(a);el.value='';renderTodayTasks()}
function toggleTodayTask(id){let a=todayTasks().map(x=>x.id===id?Object.assign({},x,{done:!x.done}):x);saveTodayTasks(a);renderTodayTasks()}
function deleteTodayTask(id){saveTodayTasks(todayTasks().filter(x=>x.id!==id));renderTodayTasks()}
function clearDoneTasks(){saveTodayTasks(todayTasks().filter(x=>!x.done));renderTodayTasks()}
function renderTodayTasks(){let a=todayTasks(),el=$('todayTaskList');if(!el)return;if(!a.length){el.innerHTML='<div class="box">아직 적어둔 오늘 할 일이 없어요.</div>';return}el.innerHTML=a.map(x=>'<div class="item"><b style="'+(x.done?'text-decoration:line-through;opacity:.55':'')+'">'+(x.done?'✅ ':'⬜ ')+esc(x.text)+'</b><div class="two"><button class="mini" onclick="toggleTodayTask('+x.id+')">'+(x.done?'다시 하기':'끝냈어요')+'</button><button class="mini danger" onclick="deleteTodayTask('+x.id+')">삭제</button></div></div>').join('')}
"""
 html=html.replace('</script>',extra_js+'</script>')
 return HTMLResponse(html)

@app.post("/api/v1/phone-help")
def phone_help(req:PhoneHelpRequest):
 task=req.task.strip(); phone_type=req.phone_type.strip() or "모르겠어요"; detail=req.detail.strip()
 if not task: raise HTTPException(400,"EMPTY_TASK")
 client,model=_client(); prompt=f'''너는 한국 시니어를 위한 휴대폰 사용 도우미다. 휴대폰 종류는 {phone_type}. 사용자가 하고 싶은 일은 "{task}"이다. 현재 화면 정보나 추가 요청은 "{detail}"이다. 한 번에 너무 많은 단계를 말하지 않는다. 가장 먼저 해야 할 행동 1개를 첫 줄에 아주 크게 이해될 정도로 분명하게 말하고, 필요하면 이어서 최대 2단계까지만 설명한다. 버튼 이름은 화면에서 찾기 쉽게 따옴표로 표시한다. 화면이나 기종에 따라 다를 수 있으면 추측하지 말고 사용자가 현재 화면에 보이는 글자를 알려 달라고 한다. 결제, 송금, 비밀번호, 인증번호, 계정 삭제처럼 민감한 행동은 바로 누르라고 하지 말고 반드시 확인 경고를 한다. 앱 설치나 설정 변경은 되돌리는 방법도 짧게 알려준다. 어려운 전문용어를 피하고 한국어 존댓말을 쓴다.'''
 try:
  r=client.responses.create(model=model,input=[{"role":"system","content":[{"type":"input_text","text":prompt}]},{"role":"user","content":[{"type":"input_text","text":task}]}]); return {"answer":r.output_text.strip()}
 except Exception as e:
  print(f"AI_PHONE_HELP_ERROR:{type(e).__name__}:{str(e)[:800]}",flush=True); raise HTTPException(502,"AI_PHONE_HELP_FAILED")

@app.post("/api/v1/disposal")
def disposal(req:DisposalRequest):
 item=req.item.strip(); region=req.region.strip()
 if not item: raise HTTPException(400,"EMPTY_ITEM")
 client,model=_client(); region_rule=f"사용자 지역은 {region}이다. 지역별 차이가 있을 수 있으면 이 지역의 정확한 규칙을 아는 척하지 말고 관할 구청/주민센터 확인을 안내한다." if region else "지역이 입력되지 않았다. 지역별 차이가 있는 항목은 관할 구청/주민센터 확인이 필요하다고 말한다."
 prompt=f'''너는 한국 시니어를 위한 분리배출 도우미다. {region_rule} 사용자가 버리려는 물건을 보고 가장 일반적인 한국 분리배출 원칙으로 안내한다. 첫 줄에 '결론: ...'으로 버릴 방법을 말한다. 다음에 1) 준비할 것 2) 버리는 곳/방법 3) 조심할 점을 아주 쉬운 말로 최대 4줄 안에서 설명한다. 깨진 유리, 칼날, 배터리, 형광등, 약, 전자제품처럼 다칠 수 있거나 별도 수거가 필요한 것은 안전 주의를 먼저 포함한다. 확실하지 않은 품목은 추측하지 말고 '지역 확인 필요'라고 명확히 말한다. 재활용 가능 여부를 단정하기 어려우면 단정하지 않는다.'''
 try:
  r=client.responses.create(model=model,input=[{"role":"system","content":[{"type":"input_text","text":prompt}]},{"role":"user","content":[{"type":"input_text","text":item}]}]); return {"answer":r.output_text.strip()}
 except Exception as e:
  print(f"AI_DISPOSAL_ERROR:{type(e).__name__}:{str(e)[:800]}",flush=True); raise HTTPException(502,"AI_DISPOSAL_FAILED")

@app.post("/api/v1/cooking")
def cooking(req:CookingRequest):
 ingredients=req.ingredients.strip(); preference=req.preference.strip() or "쉽고 간단하게"
 if not ingredients: raise HTTPException(400,"EMPTY_INGREDIENTS")
 client,model=_client(); prompt=f'''너는 한국 시니어를 위한 집밥 요리 도우미다. 사용자가 가진 재료를 중심으로 실제 만들기 쉬운 음식 한 가지를 추천한다. 원하는 방식은 {preference}. 답변은 반드시 쉬운 한국어 존댓말로 한다. 첫 줄에 음식 이름, 다음에 필요한 재료, 그 다음 1번부터 최대 5번까지 조리 순서를 쓴다. 불이나 칼을 사용할 때 조심할 점이 있으면 마지막 한 줄에 짧게 알려준다. 사용자가 말하지 않은 특별한 재료를 많이 요구하지 않는다. 질병 치료나 건강 효능을 단정하지 않는다.'''
 try:
  r=client.responses.create(model=model,input=[{"role":"system","content":[{"type":"input_text","text":prompt}]},{"role":"user","content":[{"type":"input_text","text":ingredients}]}]); return {"answer":r.output_text.strip()}
 except Exception as e:
  print(f"AI_COOKING_ERROR:{type(e).__name__}:{str(e)[:800]}",flush=True); raise HTTPException(502,"AI_COOKING_FAILED")

@app.post("/api/v1/compose-message")
def compose_message(req:MessageRequest):
 content=req.content.strip(); tone=req.tone.strip() or "따뜻하고 자연스럽게"
 if not content: raise HTTPException(400,"EMPTY_CONTENT")
 client,model=_client(); prompt=f'''너는 한국 시니어를 위한 문자 작성 도우미다. 사용자가 말한 핵심 내용은 바꾸지 말고 실제로 바로 보낼 수 있는 문자 한 통을 작성한다. 말투는 {tone}. 지나치게 길거나 과장하지 말고 자연스러운 한국어 존댓말을 쓴다. 설명, 제목, 따옴표 없이 완성된 문자 본문만 출력한다. 사용자가 현재 문장과 수정 요청을 주면 수정 요청을 반영한 최종 문장만 출력한다.'''
 try:
  r=client.responses.create(model=model,input=[{"role":"system","content":[{"type":"input_text","text":prompt}]},{"role":"user","content":[{"type":"input_text","text":content}]}]); return {"message":r.output_text.strip()}
 except Exception as e:
  print(f"AI_MESSAGE_ERROR:{type(e).__name__}:{str(e)[:800]}",flush=True); raise HTTPException(502,"AI_MESSAGE_FAILED")

@app.post("/api/v1/ask")
def ask(req:AskRequest):
 q=req.question.strip()
 if not q: raise HTTPException(400,"EMPTY_QUESTION")
 client,model=_client(); prompt='''너는 한국 시니어의 AI 생활비서다. 사용자가 지금 해결하려는 일을 먼저 파악한다. 쉬운 한국어 존댓말로 결론부터 짧게 답한다. 필요하면 지금 할 일을 최대 3단계로 제시한다. 의료·법률·금융은 단정하지 않는다. 사기·송금·비밀번호·인증번호가 관련되면 행동을 서두르지 말고 공식기관이나 가족에게 확인하도록 한다. 실시간 정보는 꾸며내지 않는다.'''
 try:
  r=client.responses.create(model=model,input=[{"role":"system","content":[{"type":"input_text","text":prompt}]},{"role":"user","content":[{"type":"input_text","text":q}]}]); return {"answer":r.output_text.strip()}
 except Exception as e:
  print(f"AI_ASK_ERROR:{type(e).__name__}:{str(e)[:800]}",flush=True); raise HTTPException(502,"AI_ASK_FAILED")

@app.post("/api/v1/analyze-image")
async def analyze_image(image:UploadFile=File(...),mode:Literal["safe","explain","screen"]=Form(...),voice_context:str=Form("")):
 raw=await image.read()
 if not raw or len(raw)>MAX_BYTES: raise HTTPException(413,"IMAGE_TOO_LARGE")
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
const VERSION='5.4.0';
const OPENAI_URL='https://api.openai.com/v1/responses';

function json(data,status=200){return new Response(JSON.stringify(data),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'}})}
function extractText(data){try{for(const o of data.output||[])for(const c of o.content||[])if(c.type==='output_text'&&c.text)return c.text.trim()}catch{} return ''}
async function callOpenAI(env,input){if(!env.OPENAI_API_KEY)throw new Error('AI_PROVIDER_NOT_CONFIGURED');const r=await fetch(OPENAI_URL,{method:'POST',headers:{'authorization':`Bearer ${env.OPENAI_API_KEY}`,'content-type':'application/json'},body:JSON.stringify({model:env.OPENAI_MODEL||'gpt-4.1-mini',input})});if(!r.ok)throw new Error('OPENAI_'+r.status);return extractText(await r.json())}
function bytesToBase64(buf){const bytes=new Uint8Array(buf);let out='';const chunk=0x8000;for(let i=0;i<bytes.length;i+=chunk)out+=String.fromCharCode(...bytes.subarray(i,i+chunk));return btoa(out)}
async function aiText(env,system,user){return callOpenAI(env,[{role:'system',content:[{type:'input_text',text:system}]},{role:'user',content:[{type:'input_text',text:user}]}])}

async function handleApi(request,env,url){
 try{
  if(url.pathname==='/health')return json({ok:true,provider_configured:!!env.OPENAI_API_KEY,model:env.OPENAI_MODEL||'gpt-4.1-mini',version:VERSION,platform:'cloudflare'});
  if(request.method!=='POST')return json({error:'METHOD_NOT_ALLOWED'},405);
  if(url.pathname==='/api/v1/ask'){
   const {question=''}=await request.json(); if(!question.trim())return json({error:'EMPTY_QUESTION'},400);
   const a=await aiText(env,'너는 한국 시니어의 AI 생활비서다. 쉬운 한국어 존댓말로 결론부터 짧게 답하고, 필요하면 지금 할 일을 최대 3단계로 제시한다. 의료·법률·금융은 단정하지 않는다. 사기·송금·비밀번호·인증번호가 관련되면 행동을 서두르지 말고 공식기관이나 가족에게 확인하도록 한다. 실시간 정보는 꾸며내지 않는다.',question.trim()); return json({answer:a});
  }
  if(url.pathname==='/api/v1/compose-message'){
   const {content='',tone='따뜻하고 자연스럽게'}=await request.json(); if(!content.trim())return json({error:'EMPTY_CONTENT'},400);
   const a=await aiText(env,`너는 한국 시니어를 위한 문자 작성 도우미다. 사용자가 말한 핵심 내용은 바꾸지 말고 실제로 바로 보낼 수 있는 문자 한 통을 작성한다. 말투는 ${tone}. 지나치게 길거나 과장하지 말고 자연스러운 한국어 존댓말을 쓴다. 설명, 제목, 따옴표 없이 완성된 문자 본문만 출력한다.`,content.trim()); return json({message:a});
  }
  if(url.pathname==='/api/v1/cooking'){
   const {ingredients='',preference='쉽고 간단하게'}=await request.json(); if(!ingredients.trim())return json({error:'EMPTY_INGREDIENTS'},400);
   const a=await aiText(env,`너는 한국 시니어를 위한 집밥 요리 도우미다. 사용자가 가진 재료를 중심으로 실제 만들기 쉬운 음식 한 가지를 추천한다. 원하는 방식은 ${preference}. 쉬운 한국어 존댓말로 음식 이름, 필요한 재료, 최대 5단계 조리 순서, 안전 주의 한 줄 순서로 답한다.`,ingredients.trim()); return json({answer:a});
  }
  if(url.pathname==='/api/v1/disposal'){
   const {item='',region=''}=await request.json(); if(!item.trim())return json({error:'EMPTY_ITEM'},400);
   const area=region?`사용자 지역은 ${region}. 지역별 규칙이 다르면 확실한 척하지 말고 관할 구청/주민센터 확인을 안내한다.`:'지역 미입력. 지역별 차이가 있으면 관할 구청/주민센터 확인을 안내한다.';
   const a=await aiText(env,`너는 한국 시니어를 위한 분리배출 도우미다. ${area} 첫 줄은 '결론:'으로 시작하고, 준비할 것, 버리는 방법, 조심할 점을 아주 쉽게 설명한다. 깨진 유리·칼날·배터리·형광등·약·전자제품은 안전을 우선한다.`,item.trim()); return json({answer:a});
  }
  if(url.pathname==='/api/v1/phone-help'){
   const {task='',phone_type='모르겠어요',detail=''}=await request.json(); if(!task.trim())return json({error:'EMPTY_TASK'},400);
   const a=await aiText(env,`너는 한국 시니어를 위한 휴대폰 사용 도우미다. 휴대폰 종류는 ${phone_type}. 한 번에 최대 2단계만 아주 쉽게 안내한다. 버튼 이름은 따옴표로 표시한다. 화면이 다르면 추측하지 말고 보이는 글자를 물어본다. 결제·송금·비밀번호·인증번호·계정 삭제는 반드시 확인 경고를 한다. 현재 화면 정보: ${detail}`,task.trim()); return json({answer:a});
  }
  if(url.pathname==='/api/v1/analyze-image'){
   const fd=await request.formData(); const image=fd.get('image'); const mode=String(fd.get('mode')||'explain'); const voice=String(fd.get('voice_context')||''); if(!(image instanceof File))return json({error:'NO_IMAGE'},400); if(image.size>12582912)return json({error:'IMAGE_TOO_LARGE'},413);
   const b64=bytesToBase64(await image.arrayBuffer()); const mime=image.type||'image/jpeg';
   const modeRule=mode==='safe'?'사기·송금·개인정보·수상한 링크·위험 신호를 우선 확인하고, 위험하면 절대로 누르거나 송금하지 말라고 먼저 말한다.':'사진 속 대상이 무엇인지 먼저 식별하고 시니어가 지금 바로 할 수 있는 행동을 가장 쉽게 설명한다.';
   const prompt=`너는 한국 시니어를 위한 사진 생활비서다. ${modeRule}\n사용자 상황: ${voice}\n사진을 보고 어려운 전문용어 없이 한국어로 답한다. 반드시 JSON만 출력한다: {"mode":"${mode}","summary":"한 문장","important_points":["최대3개"],"risk":{"level":"unknown|low|caution|high","confidence":0.0,"reasons":["..."]},"uncertainty":["..."],"next_actions":[]}`;
   const text=await callOpenAI(env,[{role:'user',content:[{type:'input_text',text:prompt},{type:'input_image',image_url:`data:${mime};base64,${b64}`}]}]); let obj; try{obj=JSON.parse(text.replace(/^```json\s*|^```\s*|```$/g,'').trim())}catch{return json({error:'INVALID_AI_JSON'},502)};
   const r=obj.risk||{}; const blocked=['high','unknown'].includes(r.level)||Number(r.confidence||0)<0.70; return json({analysis:obj,safety:{blocked_from_sensitive_action:blocked,message:blocked?'민감한 행동은 중단하고 추가 확인이 필요합니다.':'민감한 행동은 사용자 확인 후 진행합니다.'}});
  }
  return json({error:'NOT_FOUND'},404);
 }catch(e){return json({error:String(e.message||e)},502)}
}

const SENIOR_STYLE=`<style>
:root{--senior-accent:#315b57}.hero{padding:22px!important}.hero h1{font-size:34px!important;line-height:1.18!important}.hero p{font-size:19px!important;line-height:1.55!important}.ask{min-height:74px!important;font-size:22px!important}.card{min-height:128px!important;padding:16px!important}.card b{font-size:21px!important}.card small{font-size:15px!important;line-height:1.45!important}.senior-priority{border:3px solid #315b57!important;box-shadow:0 8px 22px rgba(49,91,87,.18)!important}.senior-quick{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}.senior-quick button{border:0;border-radius:18px;min-height:72px;padding:12px;background:#fff;font-size:18px;font-weight:900;color:#26302f;box-shadow:0 4px 14px rgba(33,50,47,.10)}.senior-quick button:first-child{grid-column:1/-1;background:#315b57;color:#fff;font-size:22px;min-height:82px}.senior-note{background:#eef5f2;border-radius:16px;padding:12px 14px;font-size:16px;line-height:1.5;margin:12px 0}.sectionTitle{font-size:20px!important}.version{font-size:12px!important}
@media(max-width:390px){.hero h1{font-size:31px!important}.senior-quick{grid-template-columns:1fr}.senior-quick button:first-child{grid-column:auto}}
</style>`;

const SENIOR_SCRIPT=`<script>(function(){
function byText(sel,text){return [...document.querySelectorAll(sel)].find(x=>x.textContent.includes(text))}
function enhance(){
 const hero=document.querySelector('#home .hero'); if(!hero)return;
 const h=hero.querySelector('h1'); if(h)h.textContent='말씀만 하세요. 제가 도와드릴게요.';
 const p=hero.querySelector('p'); if(p)p.innerHTML='메뉴를 찾지 않아도 됩니다.<br><b>말하거나 큰 버튼 하나만 누르세요.</b>';
 const voice=hero.querySelector('.voice'); if(voice){voice.textContent='🎙 GPT야, 이것 좀 해줘';voice.setAttribute('aria-label','음성으로 무엇이든 부탁하기')}
 const text=hero.querySelector('.text'); if(text)text.textContent='⌨ 글자로 물어보기';
 let quick=document.getElementById('seniorQuick');
 if(!quick){quick=document.createElement('div');quick.id='seniorQuick';quick.className='senior-quick';quick.innerHTML='<button onclick="voiceAsk()">🎙 그냥 말해서 부탁하기</button><button onclick="photo(\'explain\')">📷 이게 뭐야?</button><button onclick="openTravel(\'route\')">📍 어디로 가?</button><button onclick="show(\'parking\')">🚗 내 차 어디 있지?</button><button onclick="show(\'remember\')">🧠 이것 좀 기억해줘</button>';hero.insertAdjacentElement('afterend',quick)}
 const title=byText('#home .sectionTitle','AI가 특히'); if(title)title.textContent='자주 쓰는 생활 도움';
 const priorities=['이것 좀 봐줘','내 차 어디 있지?','내 기억 찾아줘','기억해 줘'];
 document.querySelectorAll('#home .card').forEach(c=>{const b=c.querySelector('b');if(b&&priorities.some(t=>b.textContent.includes(t)))c.classList.add('senior-priority')});
 const tools=document.querySelector('#home .tools'); if(tools)tools.textContent='✨ 더 많은 생활 도움 보기';
 const v=document.querySelector('#home .version'); if(v)v.textContent='시니어 AI 생활비서 · 실사용 개선판';
 if(!document.getElementById('seniorNote')){const n=document.createElement('div');n.id='seniorNote';n.className='senior-note';n.innerHTML='💡 <b>처음 쓰셔도 괜찮아요.</b> 잘못 눌러도 홈으로 돌아올 수 있고, 어려우면 그냥 말로 부탁하세요.';tools?.insertAdjacentElement('beforebegin',n)}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',enhance);else enhance();
})();</script>`;

async function appResponse(request,env,url){
 const assetUrl=new URL('/v43.html',url);
 const res=await env.ASSETS.fetch(new Request(assetUrl,request));
 if(!res.ok)return res;
 const html=await res.text();
 const body=html.replace('</head>',SENIOR_STYLE+'</head>').replace('</body>',SENIOR_SCRIPT+'</body>');
 return new Response(body,{status:res.status,headers:{'content-type':'text/html; charset=utf-8','cache-control':'no-store','x-senior-app-version':VERSION}});
}

export default {
 async fetch(request,env){
  const url=new URL(request.url);
  if(url.pathname==='/health'||url.pathname.startsWith('/api/'))return handleApi(request,env,url);
  if(url.pathname==='/'||url.pathname==='/index.html')return appResponse(request,env,url);
  return env.ASSETS.fetch(request);
 }
};
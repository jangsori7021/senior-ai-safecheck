export async function analyzeOnServer(file, mode, voiceContext=""){
  const fd=new FormData();
  fd.append("image",file);
  fd.append("mode",mode);
  fd.append("voice_context",voiceContext);
  const r=await fetch("/api/v1/analyze-image",{method:"POST",body:fd});
  if(!r.ok) throw new Error(await r.text());
  return await r.json();
}

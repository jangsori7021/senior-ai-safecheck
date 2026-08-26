const CACHE='senior-ai-life-v372';
const STATIC=['/manifest.json','/icon.svg'];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(STATIC)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
  const req=event.request;
  if(req.method!=='GET') return;
  if(req.mode==='navigate'){
    event.respondWith(fetch(req,{cache:'no-store'}));
    return;
  }
  const url=new URL(req.url);
  if(url.origin===self.location.origin && (url.pathname==='/manifest.json' || url.pathname==='/icon.svg')){
    event.respondWith(fetch(req,{cache:'no-store'}).catch(()=>caches.match(req)));
  }
});
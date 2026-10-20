// pass-through service worker (omogućava instalaciju; podaci se uvek čitaju sa mreže)
self.addEventListener('install',e=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',()=>{});

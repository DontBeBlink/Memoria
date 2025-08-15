const CACHE = 'memoria-v3';
const ASSETS = [
  './',
  './index.html',
  './web/memories.html',
  './web/agenda.html',
  './web/backup.html',
  './web/settings.html',
  './web/js/api.js',
  './web/js/ui.js',
  './web/js/dictation.js',
  './manifest.json',
  './service-worker.js'
];

// Queue for offline requests
const QUEUE_DB = 'memoria-queue';
const QUEUE_STORE = 'requests';

// Initialize IndexedDB for request queue
async function initDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(QUEUE_DB, 1);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        const store = db.createObjectStore(QUEUE_STORE, { keyPath: 'id', autoIncrement: true });
        store.createIndex('timestamp', 'timestamp', { unique: false });
      }
    };
  });
}

// Queue a request for later
async function queueRequest(request, body) {
  try {
    const db = await initDB();
    const transaction = db.transaction([QUEUE_STORE], 'readwrite');
    const store = transaction.objectStore(QUEUE_STORE);
    
    const requestData = {
      url: request.url,
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      body: body,
      timestamp: Date.now()
    };
    
    await new Promise((resolve, reject) => {
      const req = store.add(requestData);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    
    // Register background sync
    if ('serviceWorker' in self && 'sync' in self.registration) {
      await self.registration.sync.register('background-sync');
    }
    
    // Notify clients about queue update
    await notifyClients({ type: 'queue-updated' });
  } catch (error) {
    console.error('Failed to queue request:', error);
  }
}

// Get queued requests count
async function getQueueCount() {
  try {
    const db = await initDB();
    const transaction = db.transaction([QUEUE_STORE], 'readonly');
    const store = transaction.objectStore(QUEUE_STORE);
    
    return new Promise((resolve, reject) => {
      const req = store.count();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  } catch (error) {
    console.error('Failed to get queue count:', error);
    return 0;
  }
}

// Process queued requests
async function processQueue() {
  try {
    const db = await initDB();
    const transaction = db.transaction([QUEUE_STORE], 'readwrite');
    const store = transaction.objectStore(QUEUE_STORE);
    
    const requests = await new Promise((resolve, reject) => {
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    
    for (const requestData of requests) {
      try {
        const response = await fetch(requestData.url, {
          method: requestData.method,
          headers: requestData.headers,
          body: requestData.body
        });
        
        if (response.ok) {
          // Remove successful request from queue
          await new Promise((resolve, reject) => {
            const deleteReq = store.delete(requestData.id);
            deleteReq.onsuccess = () => resolve();
            deleteReq.onerror = () => reject(deleteReq.error);
          });
        }
      } catch (error) {
        console.log('Request still failing, keeping in queue:', error);
      }
    }
    
    // Notify clients about queue update
    await notifyClients({ type: 'queue-updated' });
  } catch (error) {
    console.error('Failed to process queue:', error);
  }
}

// Notify all clients
async function notifyClients(message) {
  const clients = await self.clients.matchAll();
  clients.forEach(client => client.postMessage(message));
}

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    Promise.all([
      caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))),
      initDB()
    ])
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const { request } = e;
  const url = new URL(request.url);
  
  // Handle API requests
  if (request.method === 'POST' && (url.pathname === '/memories' || url.pathname === '/tasks')) {
    e.respondWith(handleAPIRequest(request));
    return;
  }
  
  // Handle GET requests (static assets)
  if (request.method === 'GET') {
    e.respondWith(
      caches.match(request).then(cached => cached || fetch(request).catch(() => caches.match('./index.html')))
    );
  }
});

// Handle API requests with offline queueing
async function handleAPIRequest(request) {
  try {
    const body = await request.text();
    const response = await fetch(request.url, {
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      body: body
    });
    
    return response;
  } catch (error) {
    // Network failed, queue the request
    const body = await request.clone().text();
    await queueRequest(request, body);
    
    // Return a synthetic response
    return new Response(JSON.stringify({ 
      queued: true, 
      message: 'Request queued for when online' 
    }), {
      status: 202,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

// Background sync event
self.addEventListener('sync', (e) => {
  if (e.tag === 'background-sync') {
    e.waitUntil(processQueue());
  }
});

// Handle messages from clients
self.addEventListener('message', async (e) => {
  if (e.data && e.data.type === 'get-queue-count') {
    const count = await getQueueCount();
    e.ports[0].postMessage({ count });
  } else if (e.data && e.data.type === 'process-queue') {
    await processQueue();
  }
});
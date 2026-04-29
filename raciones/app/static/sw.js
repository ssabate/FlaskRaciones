const CACHE_NAME = 'raciones-cache-v1';

// We just add a basic install and activate event to be recognized as a valid Service Worker.
// In a full PWA you would cache your offline assets here.
self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

// A simple fetch handler that just passes the request to the network.
self.addEventListener('fetch', (event) => {
    event.respondWith(
        fetch(event.request).catch(() => {
            // If offline and request fails, you could return an offline page here
            return new Response('Estás sin conexión a internet.');
        })
    );
});

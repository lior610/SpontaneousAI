/**
 * Server-Sent Events (SSE) Notification Service
 */

const clients = new Map();

// Send periodic SSE comment heartbeat every 20s to keep connection active and avoid proxy read timeouts
const HEARTBEAT_INTERVAL_MS = 20000;

setInterval(() => {
  for (const [userId, userClients] of clients.entries()) {
    for (const res of userClients) {
      if (res.writableEnded || res.destroyed) {
        userClients.delete(res);
      } else {
        try {
          res.write(': heartbeat\n\n');
          if (typeof res.flush === 'function') {
            res.flush();
          }
        } catch (err) {
          userClients.delete(res);
        }
      }
    }
    if (userClients.size === 0) {
      clients.delete(userId);
    }
  }
}, HEARTBEAT_INTERVAL_MS);

export function addClient(userId, res) {
  if (!clients.has(userId)) {
    clients.set(userId, new Set());
  }
  clients.get(userId).add(res);
}

export function removeClient(userId, res) {
  if (clients.has(userId)) {
    clients.get(userId).delete(res);
    if (clients.get(userId).size === 0) {
      clients.delete(userId);
    }
  }
}

export function sendNotification(userId, type, payload) {
  const userClients = clients.get(userId);
  if (!userClients) return;

  const data = JSON.stringify({ type, payload });
  for (const res of userClients) {
    if (res.writableEnded || res.destroyed) {
      userClients.delete(res);
      continue;
    }
    try {
      // SSE format requires lines starting with 'data: ' and ending with two newlines
      res.write(`data: ${data}\n\n`);
      if (typeof res.flush === 'function') {
        res.flush();
      }
    } catch (err) {
      userClients.delete(res);
    }
  }
  if (userClients.size === 0) {
    clients.delete(userId);
  }
}

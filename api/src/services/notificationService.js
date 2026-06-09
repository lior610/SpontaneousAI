/**
 * Server-Sent Events (SSE) Notification Service
 */

const clients = new Map();

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
    // SSE format requires lines starting with 'data: ' and ending with two newlines
    res.write(`data: ${data}\n\n`);
  }
}

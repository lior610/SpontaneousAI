import express from 'express';
import * as notificationService from '../services/notificationService.js';

const router = express.Router();

router.get('/stream', (req, res) => {
  const userIdRaw = req.query.user_id;
  if (!userIdRaw) {
    return res.status(400).json({ error: 'user_id is required' });
  }
  
  const userId = parseInt(userIdRaw, 10);
  if (isNaN(userId)) {
    return res.status(400).json({ error: 'invalid user_id' });
  }

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
  });

  // SSE comment line just to open the connection
  res.write(': connected\n\n');

  notificationService.addClient(userId, res);

  req.on('close', () => {
    notificationService.removeClient(userId, res);
  });
});

export default router;

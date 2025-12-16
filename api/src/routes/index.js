import express from 'express';
import usersRouter from './users.js';
import tripsRouter from './trips.js';

const router = express.Router();

// Mount route handlers
router.use('/users', usersRouter);
router.use('/trips', tripsRouter);

export default router;


import express from 'express';
import { getLocations } from '../controllers/locationsController.js';

const router = express.Router();

router.get('/', getLocations);

export default router;

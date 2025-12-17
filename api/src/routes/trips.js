import express from 'express';
import * as tripsController from '../controllers/tripsController.js';

const router = express.Router();

router.get('/', tripsController.getTrips);
router.get('/:id', tripsController.getTripById);
router.post('/', tripsController.createTrip);
router.put('/:id', tripsController.updateTrip);
router.delete('/:id', tripsController.deleteTrip);

export default router;


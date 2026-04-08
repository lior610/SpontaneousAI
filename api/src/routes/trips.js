import express from 'express';
import * as tripsController from '../controllers/tripsController.js';

const router = express.Router();

router.get('/', tripsController.getTrips);
router.get('/:id/activities', tripsController.getTripActivities);
router.get('/:id', tripsController.getTripById);
router.post('/:id/activities/complete', tripsController.completeTripActivity);
router.post('/', tripsController.createTrip);
router.put('/:id', tripsController.updateTrip);
router.delete('/:id', tripsController.deleteTrip);

export default router;

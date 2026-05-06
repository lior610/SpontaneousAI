import express from 'express';
import * as tripsController from '../controllers/tripsController.js';
import * as locationService from '../services/locationService.js';

const router = express.Router();

router.get('/', tripsController.getTrips);
router.get('/:id/activities', tripsController.getTripActivities);
router.get('/:id', tripsController.getTripById);
router.get('/:id/next-activity', tripsController.getNextActivity);
router.post('/:id/activities/complete', tripsController.completeTripActivity);
router.post('/:id/activities/skip', tripsController.skipTripActivity);
router.post('/', tripsController.createTrip);
router.put('/:id', tripsController.updateTrip);
router.delete('/:id', tripsController.deleteTrip);

// Lightweight endpoint for periodic background location updates
router.post('/:id/location', async (req, res) => {
  try {
    const tripId = parseInt(req.params.id, 10);
    if (isNaN(tripId) || tripId <= 0) {
      return res.status(400).json({ error: 'Invalid trip ID' });
    }
    const { lat, lng } = req.body;
    await locationService.updatePosition(tripId, parseFloat(lat), parseFloat(lng));
    res.json({ ok: true });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

export default router;

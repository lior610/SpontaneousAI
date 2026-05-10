import express from 'express';
import * as tripsController from '../controllers/tripsController.js';
import * as locationService from '../services/locationService.js';
import * as usersDb from '../db/usersConnection.js';

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

// Lightweight endpoint for periodic background location updates.
// Verifies trip ownership via client-supplied user_id (consistent with other endpoints).
router.post('/:id/location', async (req, res) => {
  try {
    const tripId = parseInt(req.params.id, 10);
    if (isNaN(tripId) || tripId <= 0) {
      return res.status(400).json({ error: 'Invalid trip ID' });
    }
    const { lat, lng, user_id } = req.body;
    if (!user_id) {
      return res.status(400).json({ error: 'user_id is required' });
    }
    // Ownership check: reject if caller doesn't own this trip
    const tripCheck = await usersDb.query(
      'SELECT user_id FROM trips WHERE trip_id = $1',
      [tripId]
    );
    if (tripCheck.rows.length === 0) {
      return res.status(404).json({ error: 'Trip not found' });
    }
    if (tripCheck.rows[0].user_id !== parseInt(user_id, 10)) {
      return res.status(403).json({ error: 'Not authorized to update this trip' });
    }
    await locationService.updatePosition(tripId, parseFloat(lat), parseFloat(lng));
    res.json({ ok: true });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

export default router;

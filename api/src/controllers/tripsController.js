/**
 * Trips Controller - Handles trip-related request/response logic
 */

import * as usersDb from '../db/usersConnection.js';
import axios from 'axios';

// In-memory cache to hold arrays of recommendations returned by the Engine
const tripRecommendationsCache = new Map();

export const getTrips = async (req, res) => {
  try {
    const { user_id: queryUserId } = req.query;

    let result;
    if (queryUserId) {
      const userId = parseInt(queryUserId, 10);
      if (isNaN(userId) || userId <= 0) {
        return res.status(400).json({ error: 'user_id query must be a positive integer' });
      }
      result = await usersDb.query(
        `SELECT trip_id, user_id, destination, start_date, end_date, budget,
           preference_breakdown, max_walking_distance, preferred_transportation,
           max_travel_time_min, with_kids,
           current_lat, current_lng, timezone,
           local_hour_last_seen, day_of_week_last_seen,
           created_at, updated_at
         FROM trips WHERE user_id = $1 ORDER BY trip_id`,
        [userId]
      );
    } else {
      result = await usersDb.query(
        `SELECT trip_id, user_id, destination, start_date, end_date, budget,
           preference_breakdown, max_walking_distance, preferred_transportation,
           max_travel_time_min, with_kids,
           current_lat, current_lng, timezone,
           local_hour_last_seen, day_of_week_last_seen,
           created_at, updated_at
         FROM trips ORDER BY trip_id`
      );
    }

    const trips = result.rows.map((trip) => ({
      trip_id: trip.trip_id,
      user_id: trip.user_id,
      destination: trip.destination,
      start_date: trip.start_date,
      end_date: trip.end_date,
      budget: trip.budget ? parseFloat(trip.budget) : null,
      preference_breakdown: trip.preference_breakdown,
      max_walking_distance: trip.max_walking_distance != null ? parseFloat(trip.max_walking_distance) : null,
      preferred_transportation: trip.preferred_transportation,
      max_travel_time_min: trip.max_travel_time_min,
      with_kids: trip.with_kids,
      current_lat: trip.current_lat ? parseFloat(trip.current_lat) : null,
      current_lng: trip.current_lng ? parseFloat(trip.current_lng) : null,
      timezone: trip.timezone,
      local_hour_last_seen: trip.local_hour_last_seen,
      day_of_week_last_seen: trip.day_of_week_last_seen,
      created_at: trip.created_at,
      updated_at: trip.updated_at
    }));

    res.json({ trips });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};

export const getTripById = async (req, res) => {
  try {
    const { id } = req.params;

    // Validate id is a number
    const tripId = parseInt(id, 10);
    if (isNaN(tripId) || tripId <= 0) {
      return res.status(400).json({ 
        error: 'Invalid trip ID. Must be a positive integer' 
      });
    }

    // Query trip from database
    const result = await usersDb.query(
      `SELECT trip_id, user_id, destination, start_date, end_date, budget,
         preference_breakdown, max_walking_distance, preferred_transportation,
         max_travel_time_min, with_kids,
         current_lat, current_lng, timezone,
         local_hour_last_seen, day_of_week_last_seen,
         created_at, updated_at
       FROM trips 
       WHERE trip_id = $1`,
      [tripId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({
        error: 'Trip not found'
      });
    }

    const trip = result.rows[0];

    res.json({
      trip: {
        trip_id: trip.trip_id,
        user_id: trip.user_id,
        destination: trip.destination,
        start_date: trip.start_date,
        end_date: trip.end_date,
        budget: trip.budget ? parseFloat(trip.budget) : null,
        preference_breakdown: trip.preference_breakdown,
        max_walking_distance: trip.max_walking_distance != null ? parseFloat(trip.max_walking_distance) : null,
        preferred_transportation: trip.preferred_transportation,
        max_travel_time_min: trip.max_travel_time_min,
        with_kids: trip.with_kids,
        current_lat: trip.current_lat ? parseFloat(trip.current_lat) : null,
        current_lng: trip.current_lng ? parseFloat(trip.current_lng) : null,
        timezone: trip.timezone,
        local_hour_last_seen: trip.local_hour_last_seen,
        day_of_week_last_seen: trip.day_of_week_last_seen,
        created_at: trip.created_at,
        updated_at: trip.updated_at
      }
    });
  } catch (error) {
    console.error('Error fetching trip:', error);
    res.status(500).json({ error: error.message });
  }
};

export const createTrip = async (req, res) => {
  try {
    const {
      user_id,
      destination,
      start_date,
      end_date,
      budget,
      preference_breakdown,
      max_walking_distance,
      preferred_transportation,
      with_kids
    } = req.body;

    // Validate required fields
    if (!user_id || !destination || !start_date || !end_date) {
      return res.status(400).json({
        error: 'user_id, destination, start_date, and end_date are required'
      });
    }

    const userId = parseInt(user_id, 10);
    if (isNaN(userId) || userId <= 0) {
      return res.status(400).json({
        error: 'user_id must be a positive integer'
      });
    }

    const userCheck = await usersDb.query(
      'SELECT id FROM users WHERE id = $1',
      [userId]
    );
    if (userCheck.rows.length === 0) {
      return res.status(404).json({ error: 'User not found' });
    }

    const start = new Date(start_date);
    const end = new Date(end_date);
    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      return res.status(400).json({
        error: 'Invalid date format. Use YYYY-MM-DD or ISO 8601 format'
      });
    }
    if (end < start) {
      return res.status(400).json({
        error: 'end_date must be greater than or equal to start_date'
      });
    }

    let budgetValue = null;
    if (budget !== undefined && budget !== null) {
      budgetValue = parseFloat(budget);
      if (isNaN(budgetValue) || budgetValue < 0) {
        return res.status(400).json({
          error: 'budget must be a non-negative number'
        });
      }
    }

    // preference_breakdown: object of category -> percentage, e.g. { food: 80, nature: 60, ... }
    let preferenceBreakdownValue = null;
    if (preference_breakdown != null && typeof preference_breakdown === 'object') {
      preferenceBreakdownValue = JSON.stringify(preference_breakdown);
    }

    let maxWalkingDistanceValue = null;
    if (max_walking_distance !== undefined && max_walking_distance !== null) {
      const val = parseFloat(max_walking_distance);
      if (isNaN(val) || val < 0) {
        return res.status(400).json({ error: 'max_walking_distance must be a non-negative number (km)' });
      }
      maxWalkingDistanceValue = val;
    }

    const validTransport = ['walking', 'public', 'taxi'];
    let preferredTransportationValue = null;
    if (preferred_transportation !== undefined && preferred_transportation !== null && preferred_transportation !== '') {
      if (!validTransport.includes(preferred_transportation)) {
        return res.status(400).json({
          error: `preferred_transportation must be one of: ${validTransport.join(', ')}`
        });
      }
      preferredTransportationValue = preferred_transportation;
    }

    const withKidsValue = with_kids !== undefined ? (with_kids !== null ? Boolean(with_kids) : null) : null;

    const startDateStr = start.toISOString().split('T')[0];
    const endDateStr = end.toISOString().split('T')[0];

    // Restriction: a user cannot have overlapping trips in time
    const overlapCheck = await usersDb.query(
      `SELECT trip_id, destination, start_date, end_date
       FROM trips
       WHERE user_id = $1
         AND NOT (end_date < $2::date OR start_date > $3::date)
       ORDER BY start_date
       LIMIT 1`,
      [userId, startDateStr, endDateStr]
    );
    if (overlapCheck.rows.length > 0) {
      const conflict = overlapCheck.rows[0];
      return res.status(409).json({
        error: `Trip dates overlap with an existing trip (${conflict.destination}: ${conflict.start_date.toISOString().split('T')[0]} to ${conflict.end_date.toISOString().split('T')[0]}). You can only have one trip at a time.`,
      });
    }

    const result = await usersDb.query(
      `INSERT INTO trips (
        user_id, destination, start_date, end_date, budget, preference_breakdown,
        max_walking_distance, preferred_transportation, with_kids
      )
       VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
       RETURNING trip_id, user_id, destination, start_date, end_date, budget, preference_breakdown,
         max_walking_distance, preferred_transportation, with_kids, created_at, updated_at`,
      [userId, destination, startDateStr, endDateStr, budgetValue, preferenceBreakdownValue,
        maxWalkingDistanceValue, preferredTransportationValue, withKidsValue]
    );

    const newTrip = result.rows[0];

    res.status(201).json({
      message: 'Trip created successfully',
      trip: {
        trip_id: newTrip.trip_id,
        user_id: newTrip.user_id,
        destination: newTrip.destination,
        start_date: newTrip.start_date,
        end_date: newTrip.end_date,
        budget: newTrip.budget ? parseFloat(newTrip.budget) : null,
        preference_breakdown: newTrip.preference_breakdown,
        max_walking_distance: newTrip.max_walking_distance != null ? parseFloat(newTrip.max_walking_distance) : null,
        preferred_transportation: newTrip.preferred_transportation,
        with_kids: newTrip.with_kids,
        created_at: newTrip.created_at,
        updated_at: newTrip.updated_at
      }
    });
  } catch (error) {
    console.error('Error creating trip:', error);
    
    // Handle foreign key constraint violation
    if (error.code === '23503') {
      return res.status(404).json({ 
        error: 'User not found' 
      });
    }
    
    // Handle check constraint violation (date range)
    if (error.code === '23514') {
      return res.status(400).json({ 
        error: 'Invalid date range: end_date must be greater than or equal to start_date' 
      });
    }

    res.status(500).json({ error: error.message });
  }
};

export const updateTrip = async (req, res) => {
  try {
    const { id } = req.params;
    const { 
      destination, 
      start_date, 
      end_date, 
      budget,
      preference_breakdown,
      max_walking_distance,
      preferred_transportation,
      max_travel_time_min,
      with_kids,
      current_lat,
      current_lng,
      timezone,
      local_hour_last_seen,
      day_of_week_last_seen
    } = req.body;

    // Validate id is a number
    const tripId = parseInt(id, 10);
    if (isNaN(tripId) || tripId <= 0) {
      return res.status(400).json({ 
        error: 'Invalid trip ID. Must be a positive integer' 
      });
    }

    // Check if trip exists
    const tripCheck = await usersDb.query(
      'SELECT trip_id FROM trips WHERE trip_id = $1',
      [tripId]
    );

    if (tripCheck.rows.length === 0) {
      return res.status(404).json({ 
        error: 'Trip not found' 
      });
    }

    // Build update query dynamically based on provided fields
    const updates = [];
    const values = [];
    let paramIndex = 1;

    if (destination !== undefined) {
      if (typeof destination !== 'string' || destination.trim().length === 0) {
        return res.status(400).json({ 
          error: 'destination must be a non-empty string' 
        });
      }
      updates.push(`destination = $${paramIndex}`);
      values.push(destination.trim());
      paramIndex++;
    }

    if (start_date !== undefined) {
      const start = new Date(start_date);
      if (isNaN(start.getTime())) {
        return res.status(400).json({ 
          error: 'Invalid start_date format. Use YYYY-MM-DD or ISO 8601 format' 
        });
      }
      updates.push(`start_date = $${paramIndex}`);
      values.push(start.toISOString().split('T')[0]);
      paramIndex++;
    }

    if (end_date !== undefined) {
      const end = new Date(end_date);
      if (isNaN(end.getTime())) {
        return res.status(400).json({ 
          error: 'Invalid end_date format. Use YYYY-MM-DD or ISO 8601 format' 
        });
      }
      updates.push(`end_date = $${paramIndex}`);
      values.push(end.toISOString().split('T')[0]);
      paramIndex++;
    }

    if (budget !== undefined) {
      if (budget !== null) {
        const budgetValue = parseFloat(budget);
        if (isNaN(budgetValue) || budgetValue < 0) {
          return res.status(400).json({ 
            error: 'budget must be a non-negative number or null' 
          });
        }
        updates.push(`budget = $${paramIndex}`);
        values.push(budgetValue);
      } else {
        updates.push(`budget = $${paramIndex}`);
        values.push(null);
      }
      paramIndex++;
    }

    if (preference_breakdown !== undefined) {
      if (preference_breakdown === null) {
        updates.push(`preference_breakdown = $${paramIndex}`);
        values.push(null);
      } else if (
        typeof preference_breakdown === 'object' &&
        preference_breakdown !== null &&
        !Array.isArray(preference_breakdown)
      ) {
        updates.push(`preference_breakdown = $${paramIndex}`);
        values.push(JSON.stringify(preference_breakdown));
      } else {
        return res.status(400).json({
          error: 'preference_breakdown must be an object of category -> percentage or null'
        });
      }
      paramIndex++;
    }

    if (max_walking_distance !== undefined) {
      if (max_walking_distance !== null) {
        const val = parseFloat(max_walking_distance);
        if (isNaN(val) || val < 0) {
          return res.status(400).json({
            error: 'max_walking_distance must be a non-negative number (km) or null'
          });
        }
        updates.push(`max_walking_distance = $${paramIndex}`);
        values.push(val);
      } else {
        updates.push(`max_walking_distance = $${paramIndex}`);
        values.push(null);
      }
      paramIndex++;
    }

    if (preferred_transportation !== undefined) {
      if (preferred_transportation === null || preferred_transportation === '') {
        updates.push(`preferred_transportation = $${paramIndex}`);
        values.push(null);
      } else {
        const validTransport = ['walking', 'public', 'taxi'];
        if (!validTransport.includes(preferred_transportation)) {
          return res.status(400).json({
            error: `preferred_transportation must be one of: ${validTransport.join(', ')}`
          });
        }
        updates.push(`preferred_transportation = $${paramIndex}`);
        values.push(preferred_transportation);
      }
      paramIndex++;
    }

    // Handle max_travel_time_min
    if (max_travel_time_min !== undefined) {
      if (max_travel_time_min !== null) {
        const travelTime = parseInt(max_travel_time_min, 10);
        if (isNaN(travelTime) || travelTime < 0) {
          return res.status(400).json({ 
            error: 'max_travel_time_min must be a non-negative integer or null' 
          });
        }
        updates.push(`max_travel_time_min = $${paramIndex}`);
        values.push(travelTime);
      } else {
        updates.push(`max_travel_time_min = $${paramIndex}`);
        values.push(null);
      }
      paramIndex++;
    }

    if (with_kids !== undefined) {
      updates.push(`with_kids = $${paramIndex}`);
      values.push(with_kids !== null ? Boolean(with_kids) : null);
      paramIndex++;
    }

    // Handle coordinates
    if (current_lat !== undefined) {
      if (current_lat !== null) {
        const lat = parseFloat(current_lat);
        if (isNaN(lat) || lat < -90 || lat > 90) {
          return res.status(400).json({ 
            error: 'current_lat must be a number between -90 and 90 or null' 
          });
        }
        updates.push(`current_lat = $${paramIndex}`);
        values.push(lat);
      } else {
        updates.push(`current_lat = $${paramIndex}`);
        values.push(null);
      }
      paramIndex++;
    }
    if (current_lng !== undefined) {
      if (current_lng !== null) {
        const lng = parseFloat(current_lng);
        if (isNaN(lng) || lng < -180 || lng > 180) {
          return res.status(400).json({ 
            error: 'current_lng must be a number between -180 and 180 or null' 
          });
        }
        updates.push(`current_lng = $${paramIndex}`);
        values.push(lng);
      } else {
        updates.push(`current_lng = $${paramIndex}`);
        values.push(null);
      }
      paramIndex++;
    }

    // Handle timezone
    if (timezone !== undefined) {
      updates.push(`timezone = $${paramIndex}`);
      values.push(timezone || null);
      paramIndex++;
    }

    // Handle local_hour_last_seen
    if (local_hour_last_seen !== undefined) {
      if (local_hour_last_seen !== null) {
        const hour = parseInt(local_hour_last_seen, 10);
        if (isNaN(hour) || hour < 0 || hour > 23) {
          return res.status(400).json({ 
            error: 'local_hour_last_seen must be an integer between 0 and 23 or null' 
          });
        }
        updates.push(`local_hour_last_seen = $${paramIndex}`);
        values.push(hour);
      } else {
        updates.push(`local_hour_last_seen = $${paramIndex}`);
        values.push(null);
      }
      paramIndex++;
    }

    // Handle day_of_week_last_seen
    if (day_of_week_last_seen !== undefined) {
      if (day_of_week_last_seen !== null) {
        const day = parseInt(day_of_week_last_seen, 10);
        if (isNaN(day) || day < 0 || day > 6) {
          return res.status(400).json({ 
            error: 'day_of_week_last_seen must be an integer between 0 and 6 or null' 
          });
        }
        updates.push(`day_of_week_last_seen = $${paramIndex}`);
        values.push(day);
      } else {
        updates.push(`day_of_week_last_seen = $${paramIndex}`);
        values.push(null);
      }
      paramIndex++;
    }

    // Check if any fields to update
    if (updates.length === 0) {
      return res.status(400).json({ 
        error: 'No fields provided to update. Provide at least one updatable trip field.'
      });
    }

    // If both dates are being updated, validate the range
    let finalStartDate;
    let finalEndDate;
    if (start_date !== undefined && end_date !== undefined) {
      const start = new Date(start_date);
      const end = new Date(end_date);
      if (end < start) {
        return res.status(400).json({ 
          error: 'end_date must be greater than or equal to start_date' 
        });
      }
      finalStartDate = start.toISOString().split('T')[0];
      finalEndDate = end.toISOString().split('T')[0];
    } else if (start_date !== undefined || end_date !== undefined) {
      // If only one date is being updated, fetch the other from database
      const currentTrip = await usersDb.query(
        'SELECT user_id, start_date, end_date FROM trips WHERE trip_id = $1',
        [tripId]
      );
      
      const currentStart = start_date !== undefined 
        ? new Date(start_date) 
        : new Date(currentTrip.rows[0].start_date);
      const currentEnd = end_date !== undefined 
        ? new Date(end_date) 
        : new Date(currentTrip.rows[0].end_date);
      
      if (currentEnd < currentStart) {
        return res.status(400).json({ 
          error: 'end_date must be greater than or equal to start_date' 
        });
      }
      finalStartDate = currentStart.toISOString().split('T')[0];
      finalEndDate = currentEnd.toISOString().split('T')[0];
    }

    // Restriction: a user cannot have overlapping trips in time
    if (finalStartDate && finalEndDate) {
      const currentTrip = await usersDb.query(
        'SELECT user_id FROM trips WHERE trip_id = $1',
        [tripId]
      );
      const currentUserId = currentTrip.rows[0]?.user_id;
      const overlapCheck = await usersDb.query(
        `SELECT trip_id, destination, start_date, end_date
         FROM trips
         WHERE user_id = $1
           AND trip_id <> $2
           AND NOT (end_date < $3::date OR start_date > $4::date)
         ORDER BY start_date
         LIMIT 1`,
        [currentUserId, tripId, finalStartDate, finalEndDate]
      );
      if (overlapCheck.rows.length > 0) {
        const conflict = overlapCheck.rows[0];
        return res.status(409).json({
          error: `Updated dates overlap with another trip (${conflict.destination}: ${conflict.start_date.toISOString().split('T')[0]} to ${conflict.end_date.toISOString().split('T')[0]}). You can only have one trip at a time.`,
        });
      }
    }

    // Add updated_at timestamp
    updates.push(`updated_at = CURRENT_TIMESTAMP`);
    
    // Add trip_id to values for WHERE clause
    values.push(tripId);

    // Execute update
    const updateQuery = `
      UPDATE trips 
      SET ${updates.join(', ')} 
      WHERE trip_id = $${paramIndex}
      RETURNING trip_id, user_id, destination, start_date, end_date, budget,
        preference_breakdown, max_walking_distance, preferred_transportation,
        max_travel_time_min, with_kids,
        current_lat, current_lng, timezone,
        local_hour_last_seen, day_of_week_last_seen,
        created_at, updated_at
    `;

    const result = await usersDb.query(updateQuery, values);

    const updatedTrip = result.rows[0];

    res.json({
      message: 'Trip updated successfully',
      trip: {
        trip_id: updatedTrip.trip_id,
        user_id: updatedTrip.user_id,
        destination: updatedTrip.destination,
        start_date: updatedTrip.start_date,
        end_date: updatedTrip.end_date,
        budget: updatedTrip.budget ? parseFloat(updatedTrip.budget) : null,
        preference_breakdown: updatedTrip.preference_breakdown,
        max_walking_distance: updatedTrip.max_walking_distance != null ? parseFloat(updatedTrip.max_walking_distance) : null,
        preferred_transportation: updatedTrip.preferred_transportation,
        max_travel_time_min: updatedTrip.max_travel_time_min,
        with_kids: updatedTrip.with_kids,
        current_lat: updatedTrip.current_lat ? parseFloat(updatedTrip.current_lat) : null,
        current_lng: updatedTrip.current_lng ? parseFloat(updatedTrip.current_lng) : null,
        timezone: updatedTrip.timezone,
        local_hour_last_seen: updatedTrip.local_hour_last_seen,
        day_of_week_last_seen: updatedTrip.day_of_week_last_seen,
        created_at: updatedTrip.created_at,
        updated_at: updatedTrip.updated_at
      }
    });
  } catch (error) {
    console.error('Error updating trip:', error);
    
    // Handle check constraint violation (date range)
    if (error.code === '23514') {
      return res.status(400).json({ 
        error: 'Invalid date range: end_date must be greater than or equal to start_date' 
      });
    }

    res.status(500).json({ error: error.message });
  }
};

export const deleteTrip = async (req, res) => {
  try {
    const { id } = req.params;

    const tripId = parseInt(id, 10);
    if (isNaN(tripId) || tripId <= 0) {
      return res.status(400).json({
        error: 'Invalid trip ID. Must be a positive integer'
      });
    }

    const result = await usersDb.query(
      'DELETE FROM trips WHERE trip_id = $1 RETURNING trip_id',
      [tripId]
    );

    if (result.rowCount === 0) {
      return res.status(404).json({ error: 'Trip not found' });
    }

    res.json({ message: 'Trip deleted', id: tripId });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};

// POST /api/trips/:id/activities/complete
export const completeTripActivity = async (req, res) => {
  try {
    const tripId = parseInt(req.params.id, 10);
    if (isNaN(tripId) || tripId <= 0) {
      return res.status(400).json({ error: 'Invalid trip ID. Must be a positive integer' });
    }

    const tripCheck = await usersDb.query('SELECT trip_id FROM trips WHERE trip_id = $1', [tripId]);
    if (tripCheck.rowCount === 0) {
      return res.status(404).json({ error: 'Trip not found' });
    }

    const {
      title,
      description,
      category,
      address,
      estimated_time,
      cost,
      rating,
      review_count,
      feedback,
      completed_at,
      place_id,
      lat,
      lng
    } = req.body ?? {};

    if (!title || typeof title !== 'string') {
      return res.status(400).json({ error: 'title is required' });
    }

    const completedAt = completed_at ? new Date(completed_at) : new Date();
    if (isNaN(completedAt.getTime())) {
      return res.status(400).json({ error: 'completed_at must be a valid datetime if provided' });
    }

    const parsedRating =
      rating !== undefined && rating !== null ? parseFloat(rating) : null;
    if (parsedRating !== null && (isNaN(parsedRating) || parsedRating < 0 || parsedRating > 5)) {
      return res.status(400).json({ error: 'rating must be between 0 and 5' });
    }

    const parsedReviewCount =
      review_count !== undefined && review_count !== null ? parseInt(review_count, 10) : null;
    if (parsedReviewCount !== null && (isNaN(parsedReviewCount) || parsedReviewCount < 0)) {
      return res.status(400).json({ error: 'review_count must be a non-negative integer' });
    }

    const result = await usersDb.query(
      `INSERT INTO trip_activity_logs (
         trip_id, title, description, category, address, estimated_time, cost,
         rating, review_count, feedback, completed_at
       )
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11)
       RETURNING id, trip_id, title, description, category, address, estimated_time, cost,
         rating, review_count, feedback, completed_at, created_at`,
      [
        tripId,
        title,
        description || null,
        category || null,
        address || null,
        estimated_time || null,
        cost || null,
        parsedRating,
        parsedReviewCount,
        feedback ? JSON.stringify(feedback) : null,
        completedAt.toISOString(),
      ]
    );

    const row = result.rows[0];

    // Engine Feedback & Coordinations update logic
    if (place_id) {
      const tripRow = await usersDb.query('SELECT user_id FROM trips WHERE trip_id = $1', [tripId]);
      const userId = tripRow.rows[0]?.user_id;

      if (userId) {
        let action = 'visited';
        if (feedback) {
          if (feedback.liked === true) action = 'liked';
          else if (feedback.liked === false) action = 'skipped';
        }

        try {
          const rawHost = process.env.ENGINE_HOST || '127.0.0.1';
          const engineHost = rawHost === 'localhost' ? '127.0.0.1' : rawHost;
          await axios.post(`http://${engineHost}:8000/recommendations/feedback`, {
            user_id: userId, trip_id: tripId, place_id, action
          });
        } catch (err) {
          console.error("Engine feedback forward err:", err.message);
        }
      }
    }

    if (lat != null && lng != null) {
      await usersDb.query(`UPDATE trips SET current_lat = $1, current_lng = $2 WHERE trip_id = $3`, [lat, lng, tripId]);
    }

    res.status(201).json({
      message: 'Activity completion saved',
      activity_log: {
        id: row.id,
        trip_id: row.trip_id,
        title: row.title,
        description: row.description,
        category: row.category,
        address: row.address,
        estimated_time: row.estimated_time,
        cost: row.cost,
        rating: row.rating != null ? parseFloat(row.rating) : null,
        review_count: row.review_count,
        feedback: row.feedback,
        completed_at: row.completed_at,
        created_at: row.created_at,
      },
    });
  } catch (error) {
    console.error('Error saving completed activity:', error);
    res.status(500).json({ error: error.message });
  }
};

// GET /api/trips/:id/activities
export const getTripActivities = async (req, res) => {
  try {
    const tripId = parseInt(req.params.id, 10);
    if (isNaN(tripId) || tripId <= 0) {
      return res.status(400).json({ error: 'Invalid trip ID. Must be a positive integer' });
    }

    const { completed } = req.query;
    let query = `
      SELECT id, trip_id, title, description, category, address, estimated_time, cost,
             rating, review_count, feedback, completed_at, created_at
      FROM trip_activity_logs
      WHERE trip_id = $1
    `;
    const values = [tripId];

    if (completed === 'true') {
      query += ' AND completed_at IS NOT NULL';
    }

    query += ' ORDER BY completed_at ASC, id ASC';

    const result = await usersDb.query(query, values);
    const activities = result.rows.map((row) => ({
      id: row.id,
      trip_id: row.trip_id,
      title: row.title,
      description: row.description,
      category: row.category,
      address: row.address,
      estimated_time: row.estimated_time,
      cost: row.cost,
      rating: row.rating != null ? parseFloat(row.rating) : null,
      review_count: row.review_count,
      feedback: row.feedback,
      completed_at: row.completed_at,
      created_at: row.created_at,
    }));

    res.json({ activities });
  } catch (error) {
    console.error('Error fetching trip activity logs:', error);
    res.status(500).json({ error: error.message });
  }
};

export const getNextActivity = async (req, res) => {
  try {
    const tripId = parseInt(req.params.id, 10);
    if (isNaN(tripId) || tripId <= 0) return res.status(400).json({ error: 'Invalid trip ID' });

    const tripCheck = await usersDb.query('SELECT * FROM trips WHERE trip_id = $1', [tripId]);
    if (tripCheck.rowCount === 0) return res.status(404).json({ error: 'Trip not found' });
    const trip = tripCheck.rows[0];

    // Determine coords
    let current_lat = trip.current_lat != null ? parseFloat(trip.current_lat) : null;
    let current_lng = trip.current_lng != null ? parseFloat(trip.current_lng) : null;
    if (current_lat === null || current_lng === null) {
      if (trip.destination && trip.destination.toLowerCase() === 'new york') {
        current_lat = 40.7580; current_lng = -73.9855;
      } else {
        current_lat = 51.5237; current_lng = -0.1585;
      }
    }

    const rawHost = process.env.ENGINE_HOST || '127.0.0.1';
    const engineHost = rawHost === 'localhost' ? '127.0.0.1' : rawHost;

    // Handle specific Utility Needs bypassing cache
    const specificNeed = req.query.specific_need;
    if (specificNeed) {
      try {
        const utilRes = await axios.post(`http://${engineHost}:8000/utilities/closest`, {
          parent_category: specificNeed,
          lat: current_lat,
          lng: current_lng,
          location_id: 1, // Engine gracefully maps or ignores if lat/lng are ok
          current_hour: new Date().getHours(),
          limit: 1
        });
        
        const utilList = utilRes.data;
        if (utilList && utilList.length > 0) {
          const attr = utilList[0];
          return res.json({
            activity: {
              id: attr.place_id || attr.activity_id || 'util-1',
              title: attr.name,
              description: attr.description || `A nearby location matching your immediate need for ${specificNeed}.`,
              image: '',
              rating: null,
              reviewCount: null,
              estimatedTime: attr.hours || '1 hour',
              cost: attr.budget ? `$${attr.budget}` : '$$',
              category: attr.categories && attr.categories.length > 0 ? attr.categories[0].toLowerCase() : 'general',
              address: attr.address,
              lat: attr.latitude,
              lng: attr.longitude,
              completed: false
            }
          });
        }
      } catch (err) {
        console.error("Utility fetch failed:", err.message);
      }
    }

    // Standard cached recommendation flow
    let cached = tripRecommendationsCache.get(tripId);
    if (!cached || cached.currentIndex >= cached.results.length) {
      console.log(`[API] Cache empty for trip ${tripId}, fetching from engine...`);
      try {
        const recRes = await axios.post(`http://${engineHost}:8000/recommendations/`, {
          user_id: trip.user_id,
          trip_id: tripId,
          current_location: { lat: current_lat, lng: current_lng },
          current_time: new Date().toISOString()
        });
        const data = recRes.data;
        tripRecommendationsCache.set(tripId, { results: data, currentIndex: 0 });
        cached = tripRecommendationsCache.get(tripId);
      } catch (err) {
        console.error("Recommendations fetch failed:", err.message);
        return res.status(500).json({ error: 'Failed to fetch recommendations from engine' });
      }
    }

    if (!cached || !cached.results || cached.results.length === 0) {
       return res.status(404).json({ error: 'No recommendations available right now.' });
    }

    const nextRec = cached.results[cached.currentIndex];
    cached.currentIndex++; // increment
    const attr = nextRec.attraction;
    
    res.json({
      activity: {
        id: attr.place_id || attr.activity_id,
        title: attr.name,
        description: attr.description,
        image: '',
        rating: null,
        reviewCount: null,
        estimatedTime: attr.hours || '1-2 hours',
        cost: attr.budget && attr.budget !== '0' ? `$${attr.budget}` : 'Free',
        category: attr.categories && attr.categories.length > 0 ? attr.categories[0].toLowerCase() : 'general',
        address: attr.address,
        lat: attr.latitude,
        lng: attr.longitude,
        completed: false
      }
    });

  } catch (error) {
    console.error('Error fetching next activity:', error);
    res.status(500).json({ error: error.message });
  }
};

export const skipTripActivity = async (req, res) => {
  try {
    const tripId = parseInt(req.params.id, 10);
    const { place_id } = req.body;
    
    if (!place_id) return res.status(400).json({ error: 'place_id is required' });

    const tripCheck = await usersDb.query('SELECT user_id FROM trips WHERE trip_id = $1', [tripId]);
    if (tripCheck.rowCount === 0) return res.status(404).json({ error: 'Trip not found' });
    const userId = tripCheck.rows[0].user_id;

    const rawHost = process.env.ENGINE_HOST || '127.0.0.1';
    const engineHost = rawHost === 'localhost' ? '127.0.0.1' : rawHost;
    
    try {
      await axios.post(`http://${engineHost}:8000/recommendations/feedback`, {
        user_id: userId, trip_id: tripId, place_id, action: 'skipped'
      });
    } catch(err) {
      console.error("Error sending skip feedback to engine:", err.message);
    }

    res.json({ message: 'Activity skipped' });
  } catch(error) {
    res.status(500).json({ error: error.message });
  }
};

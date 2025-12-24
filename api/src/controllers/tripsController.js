/**
 * Trips Controller - Handles trip-related request/response logic
 */

import * as usersDb from '../db/usersConnection.js';

export const getTrips = async (req, res) => {
  try {
    // TODO: Get trips from database
    res.json({ trips: [] });
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
      `SELECT trip_id, user_id, destination, start_date, end_date, budget, created_at, updated_at 
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
    const { user_id, destination, start_date, end_date, budget } = req.body;

    // Validate required fields
    if (!user_id || !destination || !start_date || !end_date) {
      return res.status(400).json({ 
        error: 'user_id, destination, start_date, and end_date are required' 
      });
    }

    // Validate user_id is a number
    const userId = parseInt(user_id, 10);
    if (isNaN(userId) || userId <= 0) {
      return res.status(400).json({ 
        error: 'user_id must be a positive integer' 
      });
    }

    // Check if user exists
    const userCheck = await usersDb.query(
      'SELECT id FROM users WHERE id = $1',
      [userId]
    );

    if (userCheck.rows.length === 0) {
      return res.status(404).json({ 
        error: 'User not found' 
      });
    }

    // Parse dates
    const start = new Date(start_date);
    const end = new Date(end_date);

    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      return res.status(400).json({ 
        error: 'Invalid date format. Use YYYY-MM-DD or ISO 8601 format' 
      });
    }

    // Validate date range
    if (end < start) {
      return res.status(400).json({ 
        error: 'end_date must be greater than or equal to start_date' 
      });
    }

    // Validate budget if provided
    let budgetValue = null;
    if (budget !== undefined && budget !== null) {
      budgetValue = parseFloat(budget);
      if (isNaN(budgetValue) || budgetValue < 0) {
        return res.status(400).json({ 
          error: 'budget must be a non-negative number' 
        });
      }
    }

    // Format dates as YYYY-MM-DD for PostgreSQL
    const startDateStr = start.toISOString().split('T')[0];
    const endDateStr = end.toISOString().split('T')[0];

    // Insert trip into database
    const result = await usersDb.query(
      `INSERT INTO trips (user_id, destination, start_date, end_date, budget) 
       VALUES ($1, $2, $3, $4, $5) 
       RETURNING trip_id, user_id, destination, start_date, end_date, budget, created_at, updated_at`,
      [userId, destination, startDateStr, endDateStr, budgetValue]
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
    const { destination, start_date, end_date, budget } = req.body;

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

    // Check if any fields to update
    if (updates.length === 0) {
      return res.status(400).json({ 
        error: 'No fields provided to update. Provide at least one of: destination, start_date, end_date, budget' 
      });
    }

    // If both dates are being updated, validate the range
    if (start_date !== undefined && end_date !== undefined) {
      const start = new Date(start_date);
      const end = new Date(end_date);
      if (end < start) {
        return res.status(400).json({ 
          error: 'end_date must be greater than or equal to start_date' 
        });
      }
    } else if (start_date !== undefined || end_date !== undefined) {
      // If only one date is being updated, fetch the other from database
      const currentTrip = await usersDb.query(
        'SELECT start_date, end_date FROM trips WHERE trip_id = $1',
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
      RETURNING trip_id, user_id, destination, start_date, end_date, budget, created_at, updated_at
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
    // TODO: Delete trip from database
    res.json({ message: 'Trip deleted', id });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};


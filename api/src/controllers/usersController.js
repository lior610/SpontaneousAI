/**
 * Users Controller - Handles user-related request/response logic
 */

import bcrypt from 'bcryptjs';
import * as usersDb from '../db/usersConnection.js';
import { buildPreferenceEmbeddingsForUser } from '../services/preferenceEmbedding.js';

// GET /api/users — minimal columns so it works with or without preference columns
export const getUsers = async (req, res) => {
  try {
    const result = await usersDb.query(
      `SELECT id, username, email FROM users ORDER BY id`
    );
    res.json({ users: result.rows });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};

// GET /api/users/:id
export const getUserById = async (req, res) => {
  try {
    const { id } = req.params;

    // Validate id is a number
    const userId = parseInt(id, 10);
    if (isNaN(userId) || userId <= 0) {
      return res.status(400).json({ 
        error: 'Invalid user ID. Must be a positive integer' 
      });
    }

    // Minimal columns so it works with or without preference columns; wizard uses PUT to update preferences
    const result = await usersDb.query(
      `SELECT id, username, email FROM users WHERE id = $1`,
      [userId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ 
        error: 'User not found' 
      });
    }

    const user = result.rows[0];

    res.json({
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
      },
    });
  } catch (error) {
    console.error('Error fetching user:', error);
    res.status(500).json({ error: error.message });
  }
};

// POST /api/users — registration: only username, email, password. Preferences are set later via wizard/update.
export const createUser = async (req, res) => {
  try {
    const { username, email, password } = req.body;

    // Validate input
    if (!username || !email || !password) {
      return res.status(400).json({
        error: 'Username, email, and password are required'
      });
    }

    // Validate email format (basic)
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return res.status(400).json({
        error: 'Please enter a valid email address'
      });
    }

    // Validate username format (alphanumeric and underscore only, 3-30 chars)
    if (!/^[a-zA-Z0-9_]{3,30}$/.test(username)) {
      return res.status(400).json({
        error: 'Username must be 3-30 characters and contain only letters, numbers, and underscores'
      });
    }

    // Validate password length (minimum 6 characters)
    if (password.length < 6) {
      return res.status(400).json({
        error: 'Password must be at least 6 characters long'
      });
    }

    // Check if username already exists
    const existingUser = await usersDb.query(
      'SELECT id FROM users WHERE username = $1',
      [username]
    );
    if (existingUser.rows.length > 0) {
      return res.status(409).json({ error: 'Username already exists' });
    }

    // Check if email already exists
    const existingEmail = await usersDb.query(
      'SELECT id FROM users WHERE email = $1',
      [email]
    );
    if (existingEmail.rows.length > 0) {
      return res.status(409).json({ error: 'Email already registered' });
    }

    const saltRounds = 10;
    const passwordHash = await bcrypt.hash(password, saltRounds);

    // Insert only signup fields; preferences are filled in later by the wizard (PUT /api/users/:id)
    const result = await usersDb.query(
      `INSERT INTO users (username, email, password_hash)
       VALUES ($1, $2, $3)
       RETURNING id, username, email`,
      [username, email, passwordHash]
    );

    const newUser = result.rows[0];

    res.status(201).json({
      message: 'User created successfully',
      user: {
        id: newUser.id,
        username: newUser.username,
        email: newUser.email
      }
    });
  } catch (error) {
    console.error('Error creating user:', error);
    res.status(500).json({ error: error.message });
  }
};

// PUT /api/users/:id
export const updateUser = async (req, res) => {
  try {
    const { id } = req.params;
    const {
      home_country,
      age_group,
      travel_style,
      pace_preference,
      preferred_start_hour,
      dietary_style,
      hunger_level,
      energy_level
    } = req.body;

    // Validate id is a number
    const userId = parseInt(id, 10);
    if (isNaN(userId) || userId <= 0) {
      return res.status(400).json({ 
        error: 'Invalid user ID. Must be a positive integer' 
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

    // Build update query dynamically based on provided fields
    const updates = [];
    const values = [];
    let paramIndex = 1;

    // Validate and add fields
    if (home_country !== undefined) {
      updates.push(`home_country = $${paramIndex}`);
      values.push(home_country || null);
      paramIndex++;
    }

    if (age_group !== undefined) {
      const validAgeGroups = ['teen', '20s', '30s', '40+'];
      if (age_group !== null && !validAgeGroups.includes(age_group)) {
        return res.status(400).json({ 
          error: `age_group must be one of: ${validAgeGroups.join(', ')} or null` 
        });
      }
      updates.push(`age_group = $${paramIndex}`);
      values.push(age_group);
      paramIndex++;
    }

    if (travel_style !== undefined) {
      const validTravelStyles = ['budget', 'balanced', 'premium'];
      if (travel_style !== null && !validTravelStyles.includes(travel_style)) {
        return res.status(400).json({ 
          error: `travel_style must be one of: ${validTravelStyles.join(', ')} or null` 
        });
      }
      updates.push(`travel_style = $${paramIndex}`);
      values.push(travel_style);
      paramIndex++;
    }

    if (pace_preference !== undefined) {
      const validPacePreferences = ['slow', 'normal', 'fast'];
      if (pace_preference !== null && !validPacePreferences.includes(pace_preference)) {
        return res.status(400).json({ 
          error: `pace_preference must be one of: ${validPacePreferences.join(', ')} or null` 
        });
      }
      updates.push(`pace_preference = $${paramIndex}`);
      values.push(pace_preference);
      paramIndex++;
    }

    if (preferred_start_hour !== undefined) {
      if (preferred_start_hour !== null) {
        const hour = parseInt(preferred_start_hour, 10);
        if (isNaN(hour) || hour < 0 || hour > 23) {
          return res.status(400).json({ 
            error: 'preferred_start_hour must be an integer between 0 and 23 or null' 
          });
        }
        updates.push(`preferred_start_hour = $${paramIndex}`);
        values.push(hour);
      } else {
        updates.push(`preferred_start_hour = $${paramIndex}`);
        values.push(null);
      }
      paramIndex++;
    }

    if (dietary_style !== undefined) {
      const validDietaryStyles = ['none', 'veg', 'vegan', 'kosher'];
      if (dietary_style !== null && !validDietaryStyles.includes(dietary_style)) {
        return res.status(400).json({ 
          error: `dietary_style must be one of: ${validDietaryStyles.join(', ')} or null` 
        });
      }
      updates.push(`dietary_style = $${paramIndex}`);
      values.push(dietary_style);
      paramIndex++;
    }

    if (hunger_level !== undefined) {
      if (hunger_level !== null) {
        const level = parseFloat(hunger_level);
        if (isNaN(level) || level < 0 || level > 5) {
          return res.status(400).json({ 
            error: 'hunger_level must be a number between 0 and 5 or null' 
          });
        }
        updates.push(`hunger_level = $${paramIndex}`);
        values.push(level);
      } else {
        updates.push(`hunger_level = $${paramIndex}`);
        values.push(null);
      }
      paramIndex++;
    }

    if (energy_level !== undefined) {
      if (energy_level !== null) {
        const level = parseFloat(energy_level);
        if (isNaN(level)) {
          return res.status(400).json({ 
            error: 'energy_level must be a number or null' 
          });
        }
        updates.push(`energy_level = $${paramIndex}`);
        values.push(level);
      } else {
        updates.push(`energy_level = $${paramIndex}`);
        values.push(null);
      }
      paramIndex++;
    }

    // Check if any fields to update
    if (updates.length === 0) {
      return res.status(400).json({ 
        error: 'No fields provided to update' 
      });
    }

    // Add updated_at timestamp
    updates.push(`updated_at = CURRENT_TIMESTAMP`);
    
    // Add user id to values for WHERE clause
    values.push(userId);

    // Execute update. RETURN only columns that exist in a minimal schema (id, username, email)
    // so we don't fail when preference columns like home_country are missing.
    const updateQuery = `
      UPDATE users 
      SET ${updates.join(', ')} 
      WHERE id = $${paramIndex}
      RETURNING id, username, email
    `;

    let result;
    try {
      result = await usersDb.query(updateQuery, values);
    } catch (updateError) {
      // If table is minimal (no preference columns), still return success so trip creation can proceed
      if (updateError.message && updateError.message.includes('does not exist')) {
        const fallback = await usersDb.query('SELECT id, username, email FROM users WHERE id = $1', [userId]);
        return res.json({
          message: 'User update skipped (preference columns not in database)',
          user: fallback.rows[0] || { id: userId, username: null, email: null }
        });
      }
      throw updateError;
    }

    const updatedUser = result.rows[0];

    const embeddingFields = [
      'home_country',
      'age_group',
      'travel_style',
      'pace_preference',
      'preferred_start_hour',
      'dietary_style',
      'hunger_level',
      'energy_level',
    ];
    if (embeddingFields.some((k) => req.body[k] !== undefined)) {
      buildPreferenceEmbeddingsForUser(userId).catch((err) => {
        console.error('[preference embedding] after updateUser:', err.message || err);
      });
    }

    res.json({
      message: 'User updated successfully',
      user: {
        id: updatedUser.id,
        username: updatedUser.username,
        email: updatedUser.email
      }
    });
  } catch (error) {
    console.error('Error updating user:', error);
    res.status(500).json({ error: error.message });
  }
};

// DELETE /api/users/:id
export const deleteUser = async (req, res) => {
  try {
    const { id } = req.params;
    // TODO: Delete user from database
    res.json({ message: 'User deleted', id });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};

// POST /api/users/login
export const loginUser = async (req, res) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({
        error: 'Username and password are required',
      });
    }

    // Only select columns needed for login; preferences are loaded via GET /api/users/:id when needed
    const result = await usersDb.query(
      `SELECT id, username, password_hash FROM users WHERE username = $1`,
      [username]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const user = result.rows[0];
    const isValid = await bcrypt.compare(password, user.password_hash);

    if (!isValid) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    res.json({
      user: {
        id: user.id,
        username: user.username,
      },
    });
  } catch (error) {
    console.error('Error logging in user:', error);
    res.status(500).json({ error: error.message });
  }
};


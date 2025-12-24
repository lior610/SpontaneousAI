/**
 * Users Controller - Handles user-related request/response logic
 */

import bcrypt from 'bcryptjs';
import * as usersDb from '../db/usersConnection.js';

// GET /api/users
export const getUsers = async (req, res) => {
  try {
    const result = await usersDb.query(
      'SELECT id, username, created_at, updated_at FROM users ORDER BY id'
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
    // TODO: Get user by ID from database
    res.json({ id, user: null });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};

// POST /api/users
export const createUser = async (req, res) => {
  try {
    const { username, password } = req.body;

    // Validate input
    if (!username || !password) {
      return res.status(400).json({ 
        error: 'Username and password are required' 
      });
    }

    // Validate username format (alphanumeric and underscore, 3-30 chars)
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
      return res.status(409).json({ 
        error: 'Username already exists' 
      });
    }

    // Hash password
    const saltRounds = 10;
    const passwordHash = await bcrypt.hash(password, saltRounds);

    // Insert user into database
    const result = await usersDb.query(
      'INSERT INTO users (username, password_hash) VALUES ($1, $2) RETURNING id, username, created_at',
      [username, passwordHash]
    );

    const newUser = result.rows[0];

    res.status(201).json({ 
      message: 'User created successfully',
      user: {
        id: newUser.id,
        username: newUser.username,
        created_at: newUser.created_at
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
    const userData = req.body;
    // TODO: Update user in database
    res.json({ message: 'User updated', id, user: userData });
  } catch (error) {
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


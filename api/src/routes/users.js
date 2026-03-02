import express from 'express';
import * as usersController from '../controllers/usersController.js';

const router = express.Router();

// Map routes to controller functions
router.get('/', usersController.getUsers);
router.get('/:id', usersController.getUserById);
router.post('/', usersController.createUser);
router.post('/login', usersController.loginUser);
router.put('/:id', usersController.updateUser);
router.delete('/:id', usersController.deleteUser);

export default router;


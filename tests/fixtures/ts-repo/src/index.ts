import express from 'express';
import { UserService } from './services/UserService';
import { User, ApiResponse } from './types';

const app = express();
const userService = new UserService();

app.get('/users', async (req, res) => {
  const users = await userService.getAll();
  const response: ApiResponse<User[]> = {
    data: users,
    status: 'success',
  };
  res.json(response);
});

app.listen(3000, () => {
  console.log('Server running on port 3000');
});

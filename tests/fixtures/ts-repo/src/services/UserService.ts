import { User, UserRole } from '../types';

export class UserService {
  private users: User[] = [];

  async getAll(): Promise<User[]> {
    return this.users;
  }

  async getById(id: number): Promise<User | undefined> {
    return this.users.find(u => u.id === id);
  }

  async create(user: Omit<User, 'id' | 'createdAt'>): Promise<User> {
    const newUser: User = {
      ...user,
      id: this.users.length + 1,
      createdAt: new Date(),
    };
    this.users.push(newUser);
    return newUser;
  }

  async delete(id: number): Promise<boolean> {
    const index = this.users.findIndex(u => u.id === id);
    if (index === -1) return false;
    this.users.splice(index, 1);
    return true;
  }
}

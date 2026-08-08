export interface User {
  id: number;
  name: string;
  email: string;
  createdAt: Date;
}

export type UserRole = 'admin' | 'user' | 'guest';

export interface ApiResponse<T> {
  data: T;
  status: 'success' | 'error';
  message?: string;
}

export enum ErrorCode {
  NOT_FOUND = 'NOT_FOUND',
  UNAUTHORIZED = 'UNAUTHORIZED',
  INTERNAL_ERROR = 'INTERNAL_ERROR',
}

export function isUser(obj: any): obj is User {
  return obj && typeof obj.id === 'number' && typeof obj.name === 'string';
}

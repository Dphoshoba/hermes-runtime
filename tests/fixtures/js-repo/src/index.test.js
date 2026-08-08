import { formatDate, capitalize } from './utils';

describe('formatDate', () => {
  test('formats date correctly', () => {
    const date = new Date('2024-01-15');
    expect(formatDate(date)).toBe('2024-01-15');
  });
});

describe('capitalize', () => {
  test('capitalizes first letter', () => {
    expect(capitalize('hello')).toBe('Hello');
  });
});

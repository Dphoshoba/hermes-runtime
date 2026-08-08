export function formatDate(date: Date): string {
  return date.toISOString().split('T')[0];
}

export function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

export const DEFAULT_CONFIG: Record<string, unknown> = {
  timeout: 5000,
  retries: 3,
};

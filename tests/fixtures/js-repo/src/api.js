import axios from 'axios';

const API_BASE = 'https://api.example.com';

export async function fetchData() {
  const response = await axios.get(`${API_BASE}/data`);
  return response.data;
}

export async function postData(payload) {
  const response = await axios.post(`${API_BASE}/data`, payload);
  return response.data;
}

export const API_ENDPOINTS = {
  users: `${API_BASE}/users`,
  posts: `${API_BASE}/posts`,
};

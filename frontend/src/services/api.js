import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const customKey = localStorage.getItem('gemini_api_key');
  if (customKey && customKey.trim()) {
    config.headers['X-Gemini-API-Key'] = customKey.trim();
  }
  return config;
});

export default api;

import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 60000, // 60s — Gemini can be slow
});

api.interceptors.request.use((config) => {
  const customKey = localStorage.getItem('gemini_api_key');
  if (customKey && customKey.trim()) {
    config.headers['X-Gemini-API-Key'] = customKey.trim();
  }
  return config;
});

// Global response error interceptor — extract human-readable message
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (!error.response) {
      // Network error / timeout
      error.friendlyMessage =
        'Cannot reach the backend server. Make sure it is running on port 8000.';
    } else {
      const data = error.response.data;
      // FastAPI structured errors: { detail: { detail: "...", code: "..." } }
      const inner = data?.detail;
      if (typeof inner === 'object' && inner?.detail) {
        error.friendlyMessage = inner.detail;
      } else if (typeof inner === 'string') {
        error.friendlyMessage = inner;
      } else if (typeof data === 'string') {
        error.friendlyMessage = data;
      } else {
        error.friendlyMessage = `Server error (HTTP ${error.response.status}). Please try again.`;
      }
    }
    return Promise.reject(error);
  }
);

export default api;

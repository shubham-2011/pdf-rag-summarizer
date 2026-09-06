import axios from 'axios';

// Ensure bypass-tunnel-reminder header is attached for tunnel proxy compatibility
axios.defaults.headers.common['bypass-tunnel-reminder'] = 'true';

// Active AWS EC2 Caddy HTTPS Backend Endpoint
const DEFAULT_CLOUD_BACKEND = 'https://3-18-112-83.sslip.io/api';

export const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  const customBackend = localStorage.getItem('custom_backend_url');
  if (customBackend) {
    return customBackend.endsWith('/api') ? customBackend : `${customBackend.replace(/\/$/, '')}/api`;
  }
  if (typeof window !== 'undefined') {
    if (window.location.port === '8000') {
      return '/api';
    }
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      return 'http://localhost:8000/api';
    }
  }
  return DEFAULT_CLOUD_BACKEND;
};

export const uploadPdfApi = async (file, apiKey = '') => {
  const formData = new FormData();
  formData.append('file', file);
  if (apiKey) {
    formData.append('api_key', apiKey);
  }
  
  const baseUrl = getApiBaseUrl();
  const response = await axios.post(`${baseUrl}/pdf/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data;
};

export const summarizePdfApi = async (documentId, apiKey = '', modelName = 'gpt-4o-mini') => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.post(`${baseUrl}/pdf/summarize`, {
    document_id: documentId,
    model_name: modelName,
    api_key: apiKey || null
  });
  return response.data;
};

export const queryChatApi = async (documentId, question, apiKey = '', modelName = 'gpt-4o-mini', enableWebSearch = false, chatHistory = [], documentIds = null, signal = null) => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.post(`${baseUrl}/chat/query`, {
    document_id: documentId,
    document_ids: documentIds,
    question: question,
    model_name: modelName,
    api_key: apiKey || null,
    enable_web_search: enableWebSearch,
    chat_history: chatHistory
  }, {
    signal: signal || undefined
  });
  return response.data;
};


import axios from 'axios';

// Active high-speed Cloudflare Tunnel backend endpoint (Zero 502/503 errors)
const DEFAULT_CLOUD_BACKEND = 'https://ice-occasions-profession-joe.trycloudflare.com/api';

export const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  const customBackend = localStorage.getItem('custom_backend_url');
  if (customBackend) {
    return customBackend.endsWith('/api') ? customBackend : `${customBackend.replace(/\/$/, '')}/api`;
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


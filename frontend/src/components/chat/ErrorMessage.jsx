import React from 'react';
import { AlertCircle, RefreshCw, WifiOff } from 'lucide-react';

export default function ErrorMessage({ error, onRetry }) {
  if (!error) return null;

  const isNetwork = error.type === 'network' || error.status === 0 || error.message?.includes('Network');
  const isServer = error.status >= 500;
  const isClient = error.status >= 400 && error.status < 500;

  let title = 'Query Failed';
  let message = error.message || 'An unexpected error occurred while searching.';
  let Icon = AlertCircle;

  if (isNetwork) {
    title = 'Connection Refused';
    message = 'Unable to reach backend service. Please ensure the local server is running on port 8000.';
    Icon = WifiOff;
  } else if (isServer) {
    title = 'Server Error (500)';
    message = error.detail || error.message || 'Retrieval pipeline encountered an internal error.';
  } else if (isClient) {
    title = 'Invalid Request';
    message = error.detail || error.message || 'The query parameters could not be processed.';
  }

  return (
    <div className="error-card animate-fade-in">
      <div className="error-header">
        <Icon size={16} strokeWidth={1.5} className="error-icon" />
        <span className="error-title">{title}</span>
      </div>
      <p className="error-body">{message}</p>
      {onRetry && (
        <button type="button" className="error-retry-btn" onClick={onRetry}>
          <RefreshCw size={12} strokeWidth={1.5} /> Retry Query
        </button>
      )}
    </div>
  );
}

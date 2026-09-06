import React, { useState, useEffect, useRef } from 'react';
import { queryChatApi } from '../api/client';
import { Bot, Trash2 } from 'lucide-react';
import MessageList from './chat/MessageList';
import Composer from './chat/Composer';

export default function RagChat({ documentId, apiKey }) {
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [enableWebSearch, setEnableWebSearch] = useState(false);
  
  const abortControllerRef = useRef(null);

  // 💾 Load persistent chat history for the active documentId from localStorage
  useEffect(() => {
    if (documentId) {
      setError(null);
      const savedChat = localStorage.getItem(`rag_chat_${documentId}`);
      if (savedChat) {
        try {
          setMessages(JSON.parse(savedChat));
        } catch (e) {
          console.error("Failed to parse saved chat history:", e);
          setMessages([]);
        }
      } else {
        setMessages([]);
      }
    } else {
      setMessages([]);
    }
  }, [documentId]);

  // 💾 Save chat history to localStorage whenever messages change
  useEffect(() => {
    if (documentId && messages.length > 0) {
      localStorage.setItem(`rag_chat_${documentId}`, JSON.stringify(messages));
    }
  }, [messages, documentId]);

  const handleClearHistory = () => {
    if (!documentId) return;
    if (window.confirm("Are you sure you want to clear chat history for this document?")) {
      localStorage.removeItem(`rag_chat_${documentId}`);
      setMessages([]);
      setError(null);
    }
  };

  const handleAbort = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setLoading(false);
  };

  const executeSend = async (questionText) => {
    const q = (questionText || inputQuery).trim();
    if (!q || !documentId || loading) return;

    setInputQuery('');
    setError(null);

    // Cancel any previous in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Build chat history context payload for backend
    const chatHistoryPayload = messages.map(m => ({
      role: m.role,
      content: m.content
    }));

    const userMessage = { role: 'user', content: q };
    setMessages(prev => [...prev, userMessage]);
    setLoading(true);

    try {
      const data = await queryChatApi(
        documentId,
        q,
        apiKey,
        null,
        enableWebSearch,
        chatHistoryPayload,
        null,
        controller.signal
      );


      const botMessage = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources || [],
        served_by: data.served_by || 'gemini_synthesis',
        finish_reason: data.finish_reason || 'stop',
        latency_ms: data.latency_ms || 0
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (err) {
      if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') {
        console.log('User cancelled the query.');
      } else {
        console.error('Chat query error:', err);
        const errObj = {
          type: err.response ? 'server' : 'network',
          status: err.response ? err.response.status : 0,
          message: err.message,
          detail: err.response?.data?.detail
        };
        setError(errObj);
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div className="chat-header-title">
          <div className="chat-header-icon">
            <Bot size={18} strokeWidth={1.5} className="text-accent" />
          </div>
          <div>
            <h2 className="chat-heading">Document Intelligence</h2>
            <p className="chat-subheading">Page-grounded retrieval & synthesis</p>
          </div>
        </div>

        <div className="chat-header-actions">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={handleClearHistory}
              title="Clear chat history for this document"
              className="clear-history-btn"
            >
              <Trash2 size={13} strokeWidth={1.5} />
              <span>Clear History</span>
            </button>
          )}
        </div>
      </div>

      <MessageList 
        messages={messages}
        loading={loading}
        error={error}
        onRetry={() => {
          if (messages.length > 0) {
            const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
            if (lastUserMsg) executeSend(lastUserMsg.content);
          }
        }}
        onSelectPrompt={(prompt) => executeSend(prompt)}
      />

      <Composer 
        inputQuery={inputQuery}
        setInputQuery={setInputQuery}
        onSend={() => executeSend()}
        loading={loading}
        onAbort={handleAbort}
        disabled={!documentId}
        enableWebSearch={enableWebSearch}
        setEnableWebSearch={setEnableWebSearch}
      />
    </div>
  );
}



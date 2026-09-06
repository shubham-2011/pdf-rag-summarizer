import React, { useEffect, useRef } from 'react';
import Message from './Message';
import ErrorMessage from './ErrorMessage';
import { Bot, Sparkles, Loader2 } from 'lucide-react';

const STARTER_PROMPTS = [
  'What is this document about?',
  'Summarize the core technical findings.',
  'How many pages and sections does this have?',
  'List the primary sections and outline.'
];

export default function MessageList({ messages, loading, error, onRetry, onSelectPrompt }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, error]);

  return (
    <div className="message-list-viewport">
      {messages.length === 0 && !loading && (
        <div className="empty-chat-state animate-fade-in">
          <div className="empty-icon-wrapper">
            <Bot size={24} strokeWidth={1.5} className="text-accent" />
          </div>
          <h3 className="empty-state-title">Document Intelligence Assistant</h3>
          <p className="empty-state-desc">
            Ask factual questions with exact page grounding, request comprehensive summaries, or navigate structural sections.
          </p>

          <div className="starter-chips-grid">
            {STARTER_PROMPTS.map((prompt, i) => (
              <button
                key={i}
                type="button"
                className="starter-chip"
                onClick={() => onSelectPrompt && onSelectPrompt(prompt)}
              >
                <Sparkles size={12} strokeWidth={1.5} className="chip-icon" />
                <span>{prompt}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {messages.map((msg, index) => (
        <Message key={index} message={msg} />
      ))}

      {loading && (
        <div className="chat-message-row bot-row loading-row animate-fade-in">
          <div className="chat-avatar">
            <div className="avatar-bot pulse">
              <Bot size={14} strokeWidth={1.5} />
            </div>
          </div>
          <div className="chat-message-bubble loading-bubble">
            <div className="loading-indicator">
              <Loader2 size={14} strokeWidth={1.5} className="animate-spin text-accent" />
              <span>Retrieving & synthesizing document passages...</span>
            </div>
          </div>
        </div>
      )}

      {error && (
        <ErrorMessage error={error} onRetry={onRetry} />
      )}

      <div ref={scrollRef} />
    </div>
  );
}

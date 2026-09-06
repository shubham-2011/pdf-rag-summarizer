import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Bot, User, Copy, Check, Cpu } from 'lucide-react';
import SourcePanel from './SourcePanel';

export default function Message({ message }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`chat-message-row ${isUser ? 'user-row' : 'bot-row'}`}>
      <div className="chat-avatar">
        {isUser ? (
          <div className="avatar-user">
            <User size={14} strokeWidth={1.5} />
          </div>
        ) : (
          <div className="avatar-bot">
            <Bot size={14} strokeWidth={1.5} />
          </div>
        )}
      </div>

      <div className="chat-message-bubble">
        <div className="message-header-bar">
          <span className="message-sender-name">
            {isUser ? 'You' : 'Document Intelligence'}
          </span>

          <div className="message-actions">
            {!isUser && message.served_by && (
              <span className="meta-tag mono-label" title={`Served by: ${message.served_by}`}>
                <Cpu size={10} strokeWidth={1.5} />
                {message.served_by.replace(/_/g, ' ')}
                {message.latency_ms ? ` · ${Math.round(message.latency_ms)}ms` : ''}
              </span>
            )}
            
            <button 
              type="button" 
              className="action-icon-btn" 
              onClick={handleCopy} 
              title="Copy response"
            >
              {copied ? <Check size={12} className="text-success" /> : <Copy size={12} strokeWidth={1.5} />}
            </button>
          </div>
        </div>

        <div className="markdown-body">
          <ReactMarkdown>
            {message.content}
          </ReactMarkdown>
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <SourcePanel sources={message.sources} />
        )}
      </div>
    </div>
  );
}

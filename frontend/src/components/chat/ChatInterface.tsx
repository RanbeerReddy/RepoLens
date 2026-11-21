import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, FileCode } from 'lucide-react';
import * as api from '@/services/api';
import type { ChatMessage } from '@/types';

interface ChatInterfaceProps {
  repoId: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ repoId }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || loading) return;

    const userMessage: ChatMessage = { role: 'user', content: question };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput('');
    setLoading(true);

    try {
      const response = await api.chat(repoId, question, updatedMessages);
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.answer,
        sources: response.sources,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Failed to get response';
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `Error: ${errMsg}`,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot className="w-12 h-12 text-gray-700 mb-4" />
            <h3 className="text-lg font-semibold text-gray-300">
              Chat with your codebase
            </h3>
            <p className="text-sm text-gray-500 mt-1 max-w-md">
              Ask questions about the repository's code, architecture, functions, and dependencies.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'assistant' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-blue-600/20 flex items-center justify-center mt-1">
                <Bot className="w-4 h-4 text-blue-400" />
              </div>
            )}
            <div
              className={`max-w-2xl ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-3'
                  : 'bg-gray-900 border border-gray-800 rounded-2xl rounded-bl-sm px-4 py-3'
              }`}
            >
              <p className="text-sm whitespace-pre-wrap leading-relaxed">
                {msg.content}
              </p>

              {/* Sources */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <p className="text-xs text-gray-400 mb-2">Sources</p>
                  <div className="flex flex-wrap gap-1.5">
                    {msg.sources.map((src, si) => (
                      <span
                        key={si}
                        className="inline-flex items-center gap-1 px-2 py-1 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-md text-xs text-gray-300 transition-colors cursor-default"
                        title={`${src.file_path} (${src.entity_type}, relevance: ${(src.relevance * 100).toFixed(0)}%)`}
                      >
                        <FileCode className="w-3 h-3 text-gray-500" />
                        {src.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gray-700 flex items-center justify-center mt-1">
                <User className="w-4 h-4 text-gray-300" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-blue-600/20 flex items-center justify-center">
              <Bot className="w-4 h-4 text-blue-400" />
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-2xl rounded-bl-sm px-4 py-3">
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 p-4 flex-shrink-0">
        <div className="flex items-end gap-3 max-w-3xl mx-auto">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about this repository..."
            rows={1}
            className="flex-1 resize-none px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            style={{ minHeight: '44px', maxHeight: '120px' }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="p-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-800 disabled:text-gray-600 text-white rounded-xl transition-colors flex-shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;

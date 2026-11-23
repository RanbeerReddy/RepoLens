import React, { useState } from "react";
import { Send, Bot, User, FileText, Sparkles } from "lucide-react";
import { ChatResponse, Repository } from "../types";
import { askChat } from "../services/api";

interface ChatViewProps {
  activeRepo: Repository;
  onNavigateToFile?: (file: string) => void;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: any[];
  llm_used?: boolean;
}

export const ChatView: React.FC<ChatViewProps> = ({
  activeRepo,
  onNavigateToFile,
}) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: `Hello! I am RepoLens. Ask me any question about the structure, auth, dependencies, or workflows in **${activeRepo.name}**. All answers are grounded in real AST and graph facts.`,
    },
  ]);
  const [inputQuery, setInputQuery] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async (queryText?: string) => {
    const q = (queryText || inputQuery).trim();
    if (!q || loading) return;

    const userMsg: Message = { role: "user", content: q };
    setMessages((prev) => [...prev, userMsg]);
    setInputQuery("");
    setLoading(true);

    try {
      const resp: ChatResponse = await askChat(activeRepo.id, q);
      const assistantMsg: Message = {
        role: "assistant",
        content: resp.answer,
        sources: resp.sources,
        llm_used: resp.llm_used,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${err.message || "Failed to process query."}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const suggestions = [
    "How does user authentication work?",
    "Where are database connections initialized?",
    "What dependencies call verify_password?",
  ];

  return (
    <div className="h-[calc(100vh-112px)] flex flex-col bg-[#0b0f19] max-w-4xl mx-auto p-4">
      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex items-start space-x-3 ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            {msg.role === "assistant" && (
              <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0">
                <Bot className="h-4 w-4 text-white" />
              </div>
            )}

            <div
              className={`max-w-2xl rounded-xl p-4 text-xs leading-relaxed ${
                msg.role === "user"
                  ? "bg-indigo-600 text-white rounded-tr-none font-medium"
                  : "bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none shadow-md"
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>

              {/* Source Citations */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-800 space-y-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                    Verified Code Sources:
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {msg.sources.map((s, sIdx) => (
                      <button
                        key={sIdx}
                        onClick={() => onNavigateToFile && onNavigateToFile(s.file_path)}
                        className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-slate-800/90 hover:bg-slate-700/80 border border-slate-700/60 text-indigo-300 font-mono text-[11px] transition-colors"
                      >
                        <FileText className="h-3 w-3" />
                        <span>{s.citation}</span>
                        <span className="text-[9px] text-slate-400 bg-slate-900 px-1 rounded">
                          {Math.round(s.relevance_score * 100)}%
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {msg.role === "user" && (
              <div className="h-8 w-8 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
                <User className="h-4 w-4 text-slate-300" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center space-x-3 text-slate-500 text-xs py-2">
            <div className="h-8 w-8 rounded-lg bg-indigo-600/50 flex items-center justify-center animate-pulse">
              <Bot className="h-4 w-4 text-white" />
            </div>
            <span>Searching hybrid index and reasoning with vLLM...</span>
          </div>
        )}
      </div>

      {/* Suggested Questions */}
      {messages.length <= 2 && (
        <div className="py-2 flex flex-wrap gap-2">
          {suggestions.map((s, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(s)}
              className="text-xs bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 px-3 py-1.5 rounded-lg flex items-center space-x-1.5 transition-colors"
            >
              <Sparkles className="h-3 w-3 text-indigo-400" />
              <span>{s}</span>
            </button>
          ))}
        </div>
      )}

      {/* Query Input Box */}
      <div className="pt-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2 bg-slate-900 border border-slate-800 rounded-xl p-2 focus-within:border-indigo-500 transition-colors"
        >
          <input
            type="text"
            placeholder="Ask anything about the codebase..."
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            disabled={loading}
            className="flex-1 bg-transparent px-3 text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={loading || !inputQuery.trim()}
            className="h-8 w-8 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-lg flex items-center justify-center transition-all active:scale-95"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
};

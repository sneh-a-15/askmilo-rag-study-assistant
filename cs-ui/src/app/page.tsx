"use client";

import { useState, useEffect, useRef } from "react";
import {
  Brain,
  Send,
  Loader2,
  Network,
  Database,
  Monitor,
  Clock,
  ChevronRight,
} from "lucide-react";

type AnswerData = {
  answer: string;
  rag_used: boolean;
  sources: number;
};

type HistoryItem = {
  subject: string;
  question: string;
  answer: string;
};

function TypingText({ text }: { text: string }) {
  const [displayed, setDisplayed] = useState("");
  const indexRef = useRef(0);

  useEffect(() => {
    setDisplayed("");
    indexRef.current = 0;

    const interval = setInterval(() => {
      if (indexRef.current < text.length) {
        setDisplayed(text.slice(0, indexRef.current + 1));
        indexRef.current++;
      } else {
        clearInterval(interval);
      }
    }, 12);

    return () => clearInterval(interval);
  }, [text]);

  return (
    <p className="text-gray-700 whitespace-pre-wrap text-sm leading-relaxed">
      {displayed}
      {displayed.length < text.length && (
        <span className="inline-block w-1 h-4 bg-blue-500 ml-0.5 animate-pulse align-middle" />
      )}
    </p>
  );
}

function AnswerSkeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      <div className="h-3 bg-gray-200 rounded w-full" />
      <div className="h-3 bg-gray-200 rounded w-5/6" />
      <div className="h-3 bg-gray-200 rounded w-4/6" />
      <div className="h-3 bg-gray-200 rounded w-full mt-4" />
      <div className="h-3 bg-gray-200 rounded w-3/4" />
      <div className="h-3 bg-gray-200 rounded w-5/6" />
      <div className="h-3 bg-gray-200 rounded w-2/3 mt-4" />
      <div className="h-3 bg-gray-200 rounded w-full" />
    </div>
  );
}

export default function Home() {
  const [subject, setSubject] = useState("CN");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AnswerData | null>(null);
  const [loading, setLoading] = useState(false);
  const [followups, setFollowups] = useState<string[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const handleSubmit = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setAnswer(null);
    setFollowups([]);

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/ask`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, subject }),
        }
      );
      const data: AnswerData = await res.json();
      setAnswer(data);

      // Save to history
      setHistory((prev) => [
        { subject, question, answer: data.answer },
        ...prev.slice(0, 9), // keep last 10
      ]);

      await fetchFollowups(question, data.answer);
    } catch (err) {
      setAnswer(null);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchFollowups = async (q: string, ans: string) => {
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/followup`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: q, subject, answer: ans }),
        }
      );
      const data = await res.json();
      const raw = data.followups || "";
      const parsed = raw
        .split(/\n+/)
        .map((line: string) => line.replace(/^\d+\.\s*/, "").trim())
        .filter(Boolean);
      setFollowups(parsed);
    } catch (err) {
      console.error("Error fetching follow-up questions:", err);
      setFollowups([]);
    }
  };

  const loadFromHistory = (item: HistoryItem) => {
    setSubject(item.subject);
    setQuestion(item.question);
    setAnswer({ answer: item.answer, rag_used: true, sources: 0 });
    setFollowups([]);
    setShowHistory(false);
  };

  const subjects = [
    { value: "CN", label: "Computer Networks", icon: Network },
    { value: "OS", label: "Operating Systems", icon: Monitor },
    { value: "DBMS", label: "Database Management", icon: Database },
  ];

  return (
    <>
      <title>AskMilo – Learn Smarter. CS Made Simple.</title>
      <main className="min-h-screen bg-gradient-to-br from-blue-100 via-cyan-100 to-blue-50 text-gray-800 font-sans p-20 relative overflow-hidden">
        <div className="flex flex-col items-center w-full">
          {/* Background blobs */}
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute top-1/4 left-1/4 w-72 h-72 bg-blue-200/30 rounded-full blur-3xl animate-pulse" />
            <div className="absolute bottom-1/4 right-1/4 w-72 h-72 bg-cyan-200/30 rounded-full blur-3xl animate-pulse" />
          </div>

          {/* Navbar */}
          <div className="absolute top-0 left-0 w-full flex justify-between items-center px-6 py-4 z-20">
            <div className="flex items-center gap-2">
              <Brain className="w-6 h-6 text-blue-600" />
              <span className="text-gray-800 text-lg font-semibold">AskMilo</span>
            </div>

            {/* History button */}
            {history.length > 0 && (
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="flex items-center gap-2 text-sm text-gray-600 hover:text-blue-600 transition-colors bg-white/70 px-3 py-1.5 rounded-full border border-gray-200 shadow-sm"
              >
                <Clock className="w-4 h-4" />
                History ({history.length})
              </button>
            )}
          </div>

          {/* History panel */}
          {showHistory && (
            <div className="absolute top-14 right-6 z-30 w-80 bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100">
                <h3 className="text-sm font-semibold text-gray-700">Recent Questions</h3>
              </div>
              <ul className="max-h-72 overflow-y-auto divide-y divide-gray-50">
                {history.map((item, idx) => (
                  <li
                    key={idx}
                    onClick={() => loadFromHistory(item)}
                    className="px-4 py-3 hover:bg-blue-50 cursor-pointer transition-colors group"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                        {item.subject}
                      </span>
                      <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-blue-400 transition-colors" />
                    </div>
                    <p className="text-sm text-gray-700 mt-1 line-clamp-2">{item.question}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="relative z-10 w-full max-w-5xl space-y-8">
            {/* Header */}
            <header className="text-center">
              <h1 className="text-5xl font-extrabold bg-gradient-to-r from-blue-600 to-cyan-600 bg-clip-text text-transparent animate-fade-in drop-shadow-sm">
                AskMilo
              </h1>
              <p className="text-gray-600 text-lg mt-2 animate-fade-in-delay">
                Your AI-Powered CS Companion
              </p>
            </header>

            <section className="grid md:grid-cols-2 gap-6">
              {/* Left panel */}
              <div className="space-y-6 animate-slide-up">
                <div>
                  <label className="text-sm font-medium text-gray-700">Choose Subject</label>
                  <div className="grid grid-cols-3 gap-3 mt-2">
                    {subjects.map((subj) => {
                      const Icon = subj.icon;
                      return (
                        <button
                          key={subj.value}
                          onClick={() => setSubject(subj.value)}
                          className={`flex items-center gap-2 p-3 rounded-md border transition-all duration-300 text-sm font-medium justify-center shadow-sm ${
                            subject === subj.value
                              ? "bg-blue-600 text-white border-blue-600 shadow-blue-200 scale-105"
                              : "bg-white text-gray-700 border-gray-200 hover:bg-blue-50 hover:border-blue-300"
                          }`}
                        >
                          <Icon className="w-5 h-5" />
                          {subj.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700">Your Question</label>
                  <textarea
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSubmit();
                      }
                    }}
                    rows={4}
                    className="w-full mt-2 p-3 rounded-md bg-white border border-gray-200 placeholder-gray-400 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-sm transition-all"
                    placeholder="e.g., What is deadlock in operating systems?"
                  />
                  <p className="text-xs text-gray-400 mt-1">Press Enter to submit</p>
                </div>

                <button
                  onClick={handleSubmit}
                  disabled={loading || !question.trim()}
                  className="w-full py-3 px-4 rounded-md bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-semibold transition-all hover:from-blue-700 hover:to-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-lg hover:shadow-blue-200"
                >
                  {loading ? (
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5 mr-2" />
                  )}
                  Get Answer
                </button>
              </div>

              {/* Right panel */}
              <div className="space-y-4 animate-slide-up delay-200">
                <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm min-h-48">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Brain className="w-5 h-5 text-blue-600" />
                      <h2 className="text-lg font-semibold text-gray-800">AI Answer</h2>
                    </div>
                    {/* {answer?.rag_used && (
                      <span className="text-xs bg-blue-50 text-blue-600 border border-blue-100 px-2 py-1 rounded-full font-medium">
                        📚 {answer.sources} source{answer.sources !== 1 ? "s" : ""}
                      </span>
                    )} */}
                  </div>

                  {loading ? (
                    <AnswerSkeleton />
                  ) : answer ? (
                    <TypingText text={answer.answer} />
                  ) : (
                    <p className="text-gray-400 text-sm">Ask a question to get started.</p>
                  )}
                </div>

                {followups.length > 0 && (
                  <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
                    <h3 className="text-gray-800 font-semibold mb-2 text-sm">
                      Follow-Up Questions
                    </h3>
                    <ul className="space-y-1">
                      {followups.map((q, idx) => (
                        <li
                          key={idx}
                          onClick={() => setQuestion(q)}
                          className="flex items-start gap-2 text-sm text-gray-600 hover:text-blue-600 cursor-pointer transition-colors group"
                        >
                          <ChevronRight className="w-4 h-4 mt-0.5 text-gray-300 group-hover:text-blue-400 shrink-0" />
                          {q}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>

        <style jsx global>{`
          @keyframes fade-in {
            0% { opacity: 0; transform: translateY(-10px); }
            100% { opacity: 1; transform: translateY(0); }
          }
          .animate-fade-in { animation: fade-in 0.6s ease-out forwards; }
          .animate-fade-in-delay { animation: fade-in 0.6s ease-out 0.2s forwards; }
          .animate-slide-up { animation: fade-in 0.6s ease-out forwards; }
          .line-clamp-2 {
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
          }
        `}</style>
      </main>
    </>
  );
}
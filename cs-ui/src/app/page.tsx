"use client";

import { useState } from "react";
import {
  Brain,
  Send,
  Loader2,
  Network,
  Database,
  Monitor,
  ArrowRight,
} from "lucide-react";

export default function Home() {
  const [subject, setSubject] = useState("CN");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<{
    answer: string;
    rag_used: boolean;
    sources: number;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [followups, setFollowups] = useState<string[]>([]);

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
      const data = await res.json();
      console.log("Response data:", data); // Debug log
      setAnswer(data);
      await fetchFollowups();
    } catch (err) {
      setAnswer(null);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchFollowups = async () => {
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/followup`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, subject }),
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
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute top-1/4 left-1/4 w-72 h-72 bg-blue-200/30 rounded-full blur-3xl animate-pulse"></div>
            <div className="absolute bottom-1/4 right-1/4 w-72 h-72 bg-cyan-200/30 rounded-full blur-3xl animate-pulse"></div>
          </div>

          <div className="absolute top-0 left-0 w-full flex justify-between items-center px-6 py-4 z-20">
            <div className="flex items-center gap-2">
              <Brain className="w-6 h-6 text-blue-600" />
              <span className="text-gray-800 text-lg font-semibold">
                AskMilo
              </span>
            </div>
            <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-full flex items-center gap-2 font-medium text-sm shadow-md transition-colors">
              Get Started <ArrowRight className="w-4 h-4" />
            </button>
          </div>

          <div className="relative z-10 w-full max-w-5xl space-y-8">
            <header className="text-center">
              <h1 className="text-5xl font-extrabold bg-gradient-to-r from-blue-600 to-cyan-600 bg-clip-text text-transparent animate-fade-in drop-shadow-sm">
                AskMilo
              </h1>
              <p className="text-gray-600 text-lg mt-2 animate-fade-in-delay">
                Your AI-Powered CS Companion
              </p>
            </header>

            <section className="grid md:grid-cols-2 gap-6">
              <div className="space-y-6 animate-slide-up">
                <div>
                  <label className="text-sm font-medium text-gray-700">
                    Choose Subject
                  </label>
                  <div className="grid grid-cols-3 gap-3 mt-2">
                    {subjects.map((subj) => {
                      const Icon = subj.icon;
                      return (
                        <button
                          key={subj.value}
                          onClick={() => setSubject(subj.value)}
                          className={`flex items-center gap-2 p-3 rounded-md border transition-all duration-300 text-sm font-medium justify-center shadow-sm ${
                            subject === subj.value
                              ? "bg-blue-600 text-white border-blue-600 shadow-blue-200"
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
                  <label className="text-sm font-medium text-gray-700">
                    Your Question
                  </label>
                  <textarea
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    rows={4}
                    className="w-full mt-2 p-3 rounded-md bg-white border border-gray-200 placeholder-gray-400 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-sm transition-all"
                    placeholder="e.g., What is deadlock in operating systems?"
                  />
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

              <div className="space-y-4 animate-slide-up delay-200">
                <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <Brain className="w-5 h-5 text-blue-600" />
                    <h2 className="text-lg font-semibold text-gray-800">
                      AI Answer
                    </h2>
                  </div>
                  {loading ? (
                    <p className="text-gray-500 animate-pulse">
                      Generating answer...
                    </p>
                  ) : answer ? (
                    <p className="text-gray-700 whitespace-pre-wrap text-sm leading-relaxed">
                      {typeof answer === 'string' ? answer : answer.answer}
                    </p>
                  ) : (
                    <p className="text-gray-700 whitespace-pre-wrap text-sm leading-relaxed">
                      No answer yet.
                    </p>
                  )}
                  {answer && typeof answer === 'object' && answer.rag_used && (
                    <p className="text-xs text-gray-500 mt-2">
                      📚 Sources used: {answer.sources}
                    </p>
                  )}
                </div>

                {followups.length > 0 && (
                  <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
                    <h3 className="text-gray-800 font-semibold mb-2 text-sm">
                      Follow-Up Questions
                    </h3>
                    <ul className="list-disc list-inside space-y-1 text-gray-600 text-sm">
                      {followups.map((q, idx) => (
                        <li
                          key={idx}
                          className="hover:text-gray-800 cursor-pointer transition-colors"
                          onClick={() => setQuestion(q)}
                        >
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

        <style jsx global>
          {`
            @keyframes fade-in {
              0% {
                opacity: 0;
                transform: translateY(-10px);
              }
              100% {
                opacity: 1;
                transform: translateY(0);
              }
            }
            .animate-fade-in {
              animation: fade-in 0.6s ease-out forwards;
            }
            .animate-fade-in-delay {
              animation: fade-in 0.6s ease-out 0.2s forwards;
            }
            .animate-slide-up {
              animation: fade-in 0.6s ease-out forwards;
            }
          `}
        </style>
      </main>
    </>
  );
}
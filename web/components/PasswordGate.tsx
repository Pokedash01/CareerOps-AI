"use client";

import { useState, useEffect } from "react";
import { Sparkles, Lock } from "lucide-react";

const STORAGE_KEY = "careerops_unlocked";

export default function PasswordGate({ children }: { children: React.ReactNode }) {
  const configured = process.env.NEXT_PUBLIC_DASHBOARD_PASSWORD;
  const [unlocked, setUnlocked] = useState(false);
  const [input, setInput] = useState("");
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!configured) {
      setUnlocked(true);
      return;
    }
    if (sessionStorage.getItem(STORAGE_KEY) === "true") {
      setUnlocked(true);
    }
  }, [configured]);

  if (!configured || unlocked) return <>{children}</>;

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card p-8 w-full max-w-sm">
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center mb-3">
            <Sparkles size={20} className="text-white" />
          </div>
          <div className="flex items-center gap-1.5 text-gray-500 text-xs mb-1">
            <Lock size={12} /> Protected
          </div>
          <h1 className="text-xl font-bold text-white">CareerOps Dashboard</h1>
          <p className="text-sm text-gray-400 mt-1">Enter the dashboard password to continue.</p>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (input === configured) {
              sessionStorage.setItem(STORAGE_KEY, "true");
              setUnlocked(true);
            } else {
              setError(true);
              setTimeout(() => setError(false), 1500);
            }
          }}
        >
          <input
            type="password"
            value={input}
            onChange={(e) => { setInput(e.target.value); setError(false); }}
            placeholder="Password"
            className={`input w-full text-center mb-3 ${
              error ? "border-rose-500/50 focus:ring-rose-500/40 focus:border-rose-500/50" : ""
            }`}
            autoFocus
          />
          <button type="submit" className="btn-primary w-full justify-center">
            Unlock
          </button>
          {error && <p className="text-xs text-rose-400 mt-2 text-center">Wrong password</p>}
        </form>
      </div>
    </div>
  );
}

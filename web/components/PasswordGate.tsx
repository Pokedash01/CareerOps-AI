"use client";

import { useState, useEffect } from "react";

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
    <div className="min-h-screen flex items-center justify-center bg-navy-50">
      <div className="card p-8 w-full max-w-sm text-center">
        <h1 className="text-xl font-bold text-navy-900 mb-1">CareerOps Dashboard</h1>
        <p className="text-sm text-navy-500 mb-6">Enter the dashboard password to continue.</p>
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
            className={`w-full border rounded-md px-3 py-2 text-sm mb-3 text-center ${
              error ? "border-red-400 bg-red-50" : "border-navy-200"
            }`}
            autoFocus
          />
          <button type="submit" className="btn-primary w-full">Unlock</button>
        </form>
      </div>
    </div>
  );
}

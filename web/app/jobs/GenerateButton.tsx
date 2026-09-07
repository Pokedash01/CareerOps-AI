"use client";

import { useState } from "react";

type State = "idle" | "loading" | "done" | "error";

export default function GenerateButton({
  jobId, jobTitle, company,
}: { jobId: string; jobTitle: string; company: string }) {
  const [state, setState] = useState<State>("idle");
  const [result, setResult] = useState<{ url: string; filename: string } | null>(null);
  const [error, setError] = useState<string>("");

  if (state === "done" && result) {
    return (
      <a href={result.url} target="_blank" rel="noreferrer" className="btn-primary text-xs">
        📄 Download tailored PDF
      </a>
    );
  }

  return (
    <div className="flex flex-col gap-1 items-end">
      <button
        onClick={async () => {
          setState("loading");
          setError("");
          try {
            const res = await fetch("/api/generate", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ jobId, jobTitle, company }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Generation failed");
            setResult(data);
            setState("done");
          } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
            setState("error");
          }
        }}
        disabled={state === "loading"}
        className="btn-primary text-xs"
      >
        {state === "loading" ? (
          <span className="flex items-center gap-1.5">
            <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Generating…
          </span>
        ) : "Generate tailored resume"}
      </button>
      {state === "error" && (
        <span className="text-xs text-red-500 max-w-36 text-right">{error}</span>
      )}
      <span className="text-xs text-navy-400">30–60s · LLM + PDF</span>
    </div>
  );
}

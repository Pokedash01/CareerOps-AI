"use client";

import { useState } from "react";
import { Zap, Loader2, CheckCircle2, AlertCircle } from "lucide-react";

type TriggerState = "idle" | "triggering" | "triggered" | "error";

export default function PipelineTriggerButton() {
  const [state, setState] = useState<TriggerState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function handleTrigger() {
    setState("triggering");
    setErrorMsg("");
    try {
      const res = await fetch("/api/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ref: "careerops.yml" }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Trigger failed");
      setState("triggered");
      setTimeout(() => setState("idle"), 3000);
    } catch (err) {
      setState("error");
      setErrorMsg(err instanceof Error ? err.message : "Unknown error");
      setTimeout(() => setState("idle"), 4000);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleTrigger}
        disabled={state === "triggering"}
        className={`btn-secondary flex items-center gap-1.5 text-xs ${
          state === "triggered" ? "bg-emerald-500/20 border-emerald-500/30 text-emerald-400"
          : state === "error" ? "bg-rose-500/20 border-rose-500/30 text-rose-400"
          : ""
        }`}
        title="Run the full pipeline now (job search + matching)"
      >
        {state === "triggering" && (
          <span className="flex items-center gap-1">
            <Loader2 size={12} className="animate-spin" />
            <span>Running…</span>
          </span>
        )}
        {state === "triggered" && (
          <span className="flex items-center gap-1">
            <CheckCircle2 size={12} />
            <span>Triggered!</span>
          </span>
        )}
        {state === "error" && (
          <span className="flex items-center gap-1">
            <AlertCircle size={12} />
            <span>Failed</span>
          </span>
        )}
        {(state === "idle" || state === "error") && (
          <span className="flex items-center gap-1">
            <Zap size={12} />
            <span>Run pipeline now</span>
          </span>
        )}
      </button>
      {state === "error" && (
        <span className="text-xs text-rose-400 max-w-xs truncate">{errorMsg}</span>
      )}
    </div>
  );
}
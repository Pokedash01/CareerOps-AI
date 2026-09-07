"use client";

import { useState, useEffect } from "react";
import Header from "@/components/Header";

const PREFERENCE_FIELDS = [
  {
    key: "preferred_locations",
    label: "📍 Preferred Locations",
    description: "Cities or regions you're open to working in. The bot will search for jobs in these locations.",
    placeholder: "e.g. Delhi, Remote, Bangalore",
    hint: "Separate multiple locations with commas",
    type: "tags",
  },
  {
    key: "target_roles",
    label: "💼 Target Roles",
    description: "Job titles you're actively targeting. Be specific for better matches.",
    placeholder: "e.g. Data Analyst, Business Analyst",
    hint: "Separate multiple roles with commas",
    type: "tags",
  },
  {
    key: "anti_targets",
    label: "🚫 Roles to Avoid",
    description: "Seniority levels or role types you want excluded from results.",
    placeholder: "e.g. Intern, Director, VP",
    hint: "Separate with commas, or leave empty to include everything",
    type: "tags",
  },
  {
    key: "salary_expectation",
    label: "💰 Salary Expectation",
    description: "Your expected salary range. The bot will filter out jobs below this.",
    placeholder: "e.g. 16 or 15-20",
    hint: "Enter a number or range in LPA (e.g. 16 or 15-20). Jobs below this won't be shown.",
    type: "salary",
  },
  {
    key: "open_to_internship",
    label: "🎓 Open to Internships",
    description: "Whether to include internship roles in your job matches.",
    type: "boolean",
  },
] as const;

type SaveState = "idle" | "saving" | "saved" | "error";

export default function SettingsPage() {
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [activeField, setActiveField] = useState<string | null>(null);

  // Form state for each field
  const [locations, setLocations] = useState<string[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [antiTargets, setAntiTargets] = useState<string[]>([]);
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");
  const [openToInternship, setOpenToInternship] = useState(false);

  // Load current profile from GitHub CDN
  useEffect(() => {
    async function load() {
      const repo = (window as unknown as { NEXT_PUBLIC_GITHUB_REPO?: string }).NEXT_PUBLIC_GITHUB_REPO || "Pokedash01/CareerOps-AI";
      const chatId = (window as unknown as { NEXT_PUBLIC_CHAT_ID?: string }).NEXT_PUBLIC_CHAT_ID || "1368681854";
      try {
        const res = await fetch(
          `https://raw.githubusercontent.com/${repo}/main/data/users/${chatId}/profile.json`
        );
        if (res.ok) {
          const data = await res.json();
          setProfile(data);
          setLocations(Array.isArray(data.preferred_locations) ? data.preferred_locations : []);
          setRoles(Array.isArray(data.target_roles) ? data.target_roles : []);
          setAntiTargets(Array.isArray(data.anti_targets) ? data.anti_targets : []);
          if (data.salary_expectation && typeof data.salary_expectation === "object") {
            const se = data.salary_expectation as { min_lpa?: number; max_lpa?: number };
            setSalaryMin(se.min_lpa ? String(se.min_lpa) : "");
            setSalaryMax(se.max_lpa ? String(se.max_lpa) : "");
          }
          setOpenToInternship(Boolean(data.open_to_internship));
        } else {
          // No profile yet — that's fine, use defaults
          setProfile({});
        }
      } catch {
        setProfile({});
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function parseTags(raw: string): string[] {
    return raw.split(",").map((s) => s.trim()).filter(Boolean);
  }

  async function handleSave() {
    setSaveState("saving");
    setErrorMsg("");
    try {
      const body: Record<string, unknown> = {
        preferred_locations: locations,
        target_roles: roles,
        anti_targets: antiTargets,
        open_to_internship: openToInternship,
      };
      if (salaryMin) {
        body.salary_expectation = {
          min_lpa: parseFloat(salaryMin),
          max_lpa: salaryMax ? parseFloat(salaryMax) : parseFloat(salaryMin),
        };
      }
      const res = await fetch("/api/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Save failed");
      setSaveState("saved");
      if (data.profile) setProfile(data.profile);
      setTimeout(() => setSaveState("idle"), 3000);
    } catch (err) {
      setSaveState("error");
      setErrorMsg(err instanceof Error ? err.message : "Unknown error");
      setTimeout(() => setSaveState("idle"), 4000);
    }
  }

  if (loading) {
    return (
      <main>
        <Header />
        <div className="max-w-2xl mx-auto px-6 py-12 text-center text-navy-500">
          Loading preferences…
        </div>
      </main>
    );
  }

  return (
    <main>
      <Header />
      <div className="max-w-2xl mx-auto px-6 py-8 space-y-8">
        <div>
          <h1 className="text-xl font-bold text-navy-900">Job Preferences</h1>
          <p className="text-sm text-navy-500 mt-1">
            Set your preferences here — the Telegram bot will skip these questions.
            Changes take effect on the next pipeline run.
          </p>
        </div>

        {/* Preferred Locations */}
        <PreferenceSection
          field={PREFERENCE_FIELDS[0]}
          tagsValue={locations}
          onTagsChange={setLocations}
        />

        {/* Target Roles */}
        <PreferenceSection
          field={PREFERENCE_FIELDS[1]}
          tagsValue={roles}
          onTagsChange={setRoles}
        />

        {/* Anti-targets */}
        <PreferenceSection
          field={PREFERENCE_FIELDS[2]}
          tagsValue={antiTargets}
          onTagsChange={setAntiTargets}
        />

        {/* Salary */}
        <PreferenceSection
          field={PREFERENCE_FIELDS[3]}
          salaryMin={salaryMin}
          salaryMax={salaryMax}
          onSalaryMinChange={setSalaryMin}
          onSalaryMaxChange={setSalaryMax}
        />

        {/* Internship */}
        <PreferenceSection
          field={PREFERENCE_FIELDS[4]}
          boolValue={openToInternship}
          onBoolChange={setOpenToInternship}
        />

        {/* Save button */}
        <div className="flex items-center gap-4 pt-4 border-t border-navy-100">
          <button
            onClick={handleSave}
            disabled={saveState === "saving"}
            className="btn-primary"
          >
            {saveState === "saving" ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Saving…
              </span>
            ) : saveState === "saved" ? (
              <span className="flex items-center gap-2">✅ Saved!</span>
            ) : (
              "Save Preferences"
            )}
          </button>
          {saveState === "error" && (
            <span className="text-sm text-red-500">{errorMsg}</span>
          )}
          {saveState === "idle" && (
            <span className="text-xs text-navy-400">
              Saved preferences sync to Telegram — next pipeline run uses these values.
            </span>
          )}
        </div>
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Field-specific rendering
// ---------------------------------------------------------------------------

function PreferenceSection({
  field,
  tagsValue,
  onTagsChange,
  salaryMin,
  salaryMax,
  onSalaryMinChange,
  onSalaryMaxChange,
  boolValue,
  onBoolChange,
}: {
  field: (typeof PREFERENCE_FIELDS)[number];
  tagsValue?: string[];
  onTagsChange?: (v: string[]) => void;
  salaryMin?: string;
  salaryMax?: string;
  onSalaryMinChange?: (v: string) => void;
  onSalaryMaxChange?: (v: string) => void;
  boolValue?: boolean;
  onBoolChange?: (v: boolean) => void;
}) {
  const [tagInput, setTagInput] = useState("");
  const [expanded, setExpanded] = useState(false);

  function addTag(raw: string) {
    const items = parseTags(raw);
    if (!items.length) return;
    onTagsChange?.([...(tagsValue ?? []), ...items.filter((i) => !(tagsValue ?? []).includes(i))]);
    setTagInput("");
  }

  function removeTag(tag: string) {
    onTagsChange?.((tagsValue ?? []).filter((t) => t !== tag));
  }

  return (
    <div className="card p-5 space-y-3">
      <button
        type="button"
        className="w-full flex items-start justify-between text-left"
        onClick={() => setExpanded((e) => !e)}
      >
        <div>
          <h3 className="font-semibold text-navy-800">{field.label}</h3>
          <p className="text-sm text-navy-500 mt-0.5">{field.description}</p>
        </div>
        <span className="text-navy-400 text-lg ml-4 shrink-0">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div className="pt-1 space-y-3">
          {field.type === "tags" && (
            <>
              {/* Current tags */}
              {(tagsValue ?? []).length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {(tagsValue ?? []).map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1.5 bg-navy-100 text-navy-700 text-sm px-3 py-1 rounded-full"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() => removeTag(tag)}
                        className="text-navy-400 hover:text-red-500 font-bold text-xs leading-none"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
              {/* Add input */}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === ",") {
                      e.preventDefault();
                      addTag(tagInput);
                    }
                  }}
                  placeholder={field.placeholder}
                  className="flex-1 border border-navy-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy-400"
                />
                <button
                  type="button"
                  onClick={() => addTag(tagInput)}
                  className="btn-primary text-sm"
                >
                  Add
                </button>
              </div>
              <p className="text-xs text-navy-400">{field.hint}</p>
            </>
          )}

          {field.type === "salary" && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-navy-500 block mb-1">Min (LPA)</label>
                  <input
                    type="number"
                    value={salaryMin ?? ""}
                    onChange={(e) => onSalaryMinChange?.(e.target.value)}
                    placeholder="e.g. 15"
                    className="w-full border border-navy-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy-400"
                  />
                </div>
                <div>
                  <label className="text-xs text-navy-500 block mb-1">Max (LPA)</label>
                  <input
                    type="number"
                    value={salaryMax ?? ""}
                    onChange={(e) => onSalaryMaxChange?.(e.target.value)}
                    placeholder="e.g. 20"
                    className="w-full border border-navy-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy-400"
                  />
                </div>
              </div>
              <p className="text-xs text-navy-400">
                Jobs offering less than your minimum will be filtered out.
                Leave empty to see all jobs regardless of salary.
              </p>
            </div>
          )}

          {field.type === "boolean" && (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => onBoolChange?.(!boolValue)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  boolValue ? "bg-emerald-500" : "bg-navy-200"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    boolValue ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
              <span className="text-sm text-navy-700">
                {boolValue ? "Yes, include internships" : "No, exclude internships"}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

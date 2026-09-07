"use client";

import { useState, useEffect } from "react";
import { Check, X, Save, Loader2 } from "lucide-react";
import Header from "@/components/Header";

const PREFERENCE_FIELDS = [
  {
    key: "preferred_locations",
    label: "Preferred Locations",
    description: "Cities or regions you're open to working in. The bot will search for jobs in these locations.",
    placeholder: "e.g. Delhi, Remote, Bangalore",
    hint: "Press Enter or comma to add. Separate multiple locations with commas.",
    type: "tags" as const,
  },
  {
    key: "target_roles",
    label: "Target Roles",
    description: "Job titles you're actively targeting. Be specific for better matches.",
    placeholder: "e.g. Data Analyst, Business Analyst",
    hint: "Press Enter or comma to add.",
    type: "tags" as const,
  },
  {
    key: "anti_targets",
    label: "Roles to Avoid",
    description: "Seniority levels or role types you want excluded from results.",
    placeholder: "e.g. Intern, Director, VP",
    hint: "Press Enter or comma to add. Leave empty to include everything.",
    type: "tags" as const,
  },
  {
    key: "salary_expectation",
    label: "Salary Expectation",
    description: "Your expected salary range. The bot will filter out jobs below this.",
    placeholder: "e.g. 16 or 15-20",
    hint: "Enter a number or range in LPA. Jobs below this won't be shown.",
    type: "salary" as const,
  },
  {
    key: "open_to_internship",
    label: "Open to Internships",
    description: "Whether to include internship roles in your job matches.",
    type: "boolean" as const,
  },
];

type SaveState = "idle" | "saving" | "saved" | "error";

export default function SettingsPage() {
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  // Form state
  const [locations, setLocations] = useState<string[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [antiTargets, setAntiTargets] = useState<string[]>([]);
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");
  const [openToInternship, setOpenToInternship] = useState(false);

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
        <div className="max-w-2xl mx-auto px-6 py-12 text-center text-gray-500">
          Loading preferences…
        </div>
      </main>
    );
  }

  return (
    <main>
      <Header />
      <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Job Preferences</h1>
          <p className="text-sm text-gray-400 mt-1">
            Set your preferences here — the Telegram bot will skip these questions.
            Changes take effect on the next pipeline run.
          </p>
        </div>

        <PreferenceSection
          field={PREFERENCE_FIELDS[0]}
          tagsValue={locations}
          onTagsChange={setLocations}
        />
        <PreferenceSection
          field={PREFERENCE_FIELDS[1]}
          tagsValue={roles}
          onTagsChange={setRoles}
        />
        <PreferenceSection
          field={PREFERENCE_FIELDS[2]}
          tagsValue={antiTargets}
          onTagsChange={setAntiTargets}
        />
        <PreferenceSection
          field={PREFERENCE_FIELDS[3]}
          salaryMin={salaryMin}
          salaryMax={salaryMax}
          onSalaryMinChange={setSalaryMin}
          onSalaryMaxChange={setSalaryMax}
        />
        <PreferenceSection
          field={PREFERENCE_FIELDS[4]}
          boolValue={openToInternship}
          onBoolChange={setOpenToInternship}
        />

        {/* Save row */}
        <div className="card flex items-center gap-4 flex-wrap">
          <button
            onClick={handleSave}
            disabled={saveState === "saving"}
            className="btn-primary"
          >
            {saveState === "saving" ? (
              <span className="flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" /> Saving…
              </span>
            ) : saveState === "saved" ? (
              <span className="flex items-center gap-2"><Check size={14} /> Saved</span>
            ) : (
              <span className="flex items-center gap-2"><Save size={14} /> Save Preferences</span>
            )}
          </button>
          {saveState === "error" && (
            <span className="text-sm text-rose-400">{errorMsg}</span>
          )}
          {saveState === "idle" && (
            <span className="text-xs text-gray-500">
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

  const valueCount = field.type === "tags"
    ? (tagsValue ?? []).length
    : field.type === "salary"
    ? (salaryMin ? 1 : 0)
    : 1;

  return (
    <div className="card">
      <button
        type="button"
        className="w-full flex items-start justify-between text-left"
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-white">{field.label}</h3>
            {valueCount > 0 && <span className="chip-emerald">{valueCount} set</span>}
          </div>
          <p className="text-xs text-gray-500 mt-1">{field.description}</p>
        </div>
        <span className="text-gray-500 text-xs ml-4 shrink-0 mt-1">{expanded ? "Hide" : "Edit"}</span>
      </button>

      {expanded && (
        <div className="pt-4 mt-4 border-t border-[#1F2937] space-y-3">
          {field.type === "tags" && (
            <>
              {(tagsValue ?? []).length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {(tagsValue ?? []).map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1.5 chip-blue"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() => removeTag(tag)}
                        className="text-blue-300 hover:text-rose-400 leading-none"
                        aria-label={`Remove ${tag}`}
                      >
                        <X size={12} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
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
                  className="input flex-1"
                />
                <button
                  type="button"
                  onClick={() => addTag(tagInput)}
                  className="btn-secondary"
                >
                  Add
                </button>
              </div>
              <p className="text-xs text-gray-500">{field.hint}</p>
            </>
          )}

          {field.type === "salary" && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label block mb-1.5">Min (LPA)</label>
                  <input
                    type="number"
                    value={salaryMin ?? ""}
                    onChange={(e) => onSalaryMinChange?.(e.target.value)}
                    placeholder="e.g. 15"
                    className="input w-full"
                  />
                </div>
                <div>
                  <label className="label block mb-1.5">Max (LPA)</label>
                  <input
                    type="number"
                    value={salaryMax ?? ""}
                    onChange={(e) => onSalaryMaxChange?.(e.target.value)}
                    placeholder="e.g. 20"
                    className="input w-full"
                  />
                </div>
              </div>
              <p className="text-xs text-gray-500">
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
                  boolValue ? "bg-blue-600" : "bg-[#1F2937]"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    boolValue ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
              <span className="text-sm text-gray-300">
                {boolValue ? "Yes, include internships" : "No, exclude internships"}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

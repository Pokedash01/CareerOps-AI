import { CheckCircle2, Circle, Sparkles, ArrowRight } from "lucide-react";
import Header from "@/components/Header";
import {
  getProfile,
  getPipelineState,
  isOnboardingComplete,
  getOnboardingQueue,
  CHAT_ID,
} from "@/lib/github";

export const revalidate = 300;

const ALL_PREFERENCE_FIELDS = [
  { key: "preferred_locations", label: "Preferred locations" },
  { key: "target_roles", label: "Target roles" },
  { key: "anti_targets", label: "Roles to avoid" },
  { key: "salary_expectation", label: "Salary expectation" },
  { key: "open_to_internship", label: "Open to internships" },
];

export default async function OnboardingPage() {
  const [profile, state, complete, queue] = await Promise.all([
    getProfile(),
    getPipelineState(),
    isOnboardingComplete(),
    getOnboardingQueue(),
  ]);

  const userState = state?.onboarding?.[CHAT_ID];
  const stage = userState?.stage ?? (profile ? "unknown" : "not_started");

  const statusCard = complete
    ? {
        tone: "border-emerald-500/30",
        icon: <CheckCircle2 size={28} className="text-emerald-400" />,
        title: "Onboarding complete",
        body: "All preference fields are filled. The pipeline is generating matches.",
        chip: "chip-emerald",
        chipText: "Complete",
      }
    : {
        tone: "border-amber-500/30",
        icon: <Sparkles size={28} className="text-amber-400" />,
        title:
          stage === "asking"
            ? "Bot is asking you questions"
            : stage === "reviewing"
            ? "Waiting for your confirmation in Telegram"
            : stage === "not_started"
            ? "Onboarding not started"
            : "Status unknown",
        body: "Open the Telegram bot and reply to the questions. Once you confirm the profile, the pipeline will start matching.",
        chip: "chip-amber",
        chipText: "Pending",
      };

  return (
    <main>
      <Header />
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Onboarding status</h1>
          <p className="text-sm text-gray-400 mt-1">
            Track which preference fields the bot has collected. Edit them in
            the Telegram conversation; the dashboard updates within 5 min.
          </p>
        </div>

        {/* Status card */}
        <section className={`card border ${statusCard.tone}`}>
          <div className="flex items-start gap-4">
            <div className="shrink-0">{statusCard.icon}</div>
            <div className="flex-1">
              <div className="flex items-center gap-3 flex-wrap">
                <h2 className="text-base font-semibold text-white">{statusCard.title}</h2>
                <span className={statusCard.chip}>{statusCard.chipText}</span>
              </div>
              <p className="text-sm text-gray-400 mt-1.5">{statusCard.body}</p>
            </div>
          </div>
        </section>

        {/* Preference fields */}
        {profile && (
          <section className="card">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Preference fields</h2>
            <div className="space-y-2">
              {ALL_PREFERENCE_FIELDS.map((field) => {
                const value = (profile as unknown as Record<string, unknown>)[field.key];
                const filled =
                  value !== null &&
                  value !== undefined &&
                  (Array.isArray(value) ? value.length > 0 : value !== "");
                const askingNow = queue.includes(field.key);
                return (
                  <div key={field.key} className="sub-card p-4 flex items-center gap-3">
                    {filled ? (
                      <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />
                    ) : (
                      <Circle size={18} className="text-gray-600 shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-white">{field.label}</div>
                      <div className="text-xs text-gray-500 mt-0.5 truncate">
                        {filled
                          ? renderValue(value)
                          : askingNow
                          ? "Bot is asking you right now"
                          : "Not collected yet"}
                      </div>
                    </div>
                    {filled && <span className="chip-emerald shrink-0">Filled</span>}
                    {!filled && askingNow && <span className="chip-amber shrink-0">Asking</span>}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* How to update */}
        <section className="card">
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">How to update your preferences</h2>
          <p className="text-sm text-gray-300 mb-4">
            You can edit all preference fields in the dashboard — no need to chat with the bot.
            Changes save to your profile instantly.
          </p>
          <a href="/settings" className="btn-primary inline-flex">
            Edit Preferences <ArrowRight size={14} />
          </a>
          <p className="text-xs text-gray-500 mt-4">
            Or update via Telegram: open the bot, send <code className="bg-[#1A1D23] text-gray-300 px-1.5 py-0.5 rounded">/start</code> or your resume PDF,
            and reply to the questions.
          </p>
        </section>
      </div>
    </main>
  );
}

function renderValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object" && value !== null) {
    const v = value as { min_lpa?: number; max_lpa?: number };
    if (v.min_lpa) return `₹${v.min_lpa} – ₹${v.max_lpa ?? v.min_lpa} LPA`;
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

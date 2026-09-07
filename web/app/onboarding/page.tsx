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
  { key: "preferred_locations", label: "📍 Preferred locations" },
  { key: "target_roles", label: "💼 Target roles" },
  { key: "anti_targets", label: "🚫 Roles to avoid" },
  { key: "salary_expectation", label: "💰 Salary expectation" },
  { key: "open_to_internship", label: "🎓 Open to internships" },
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

  return (
    <main>
      <Header />
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-navy-800">Onboarding status</h1>
          <p className="text-sm text-navy-500 mt-1">
            Track which preference fields the bot has collected. Edit them in
            the Telegram conversation; the dashboard updates within 5 min.
          </p>
        </div>

        <section className={`card p-5 ${complete ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200"}`}>
          <div className="flex items-start gap-3">
            <span className="text-2xl">{complete ? "✅" : "⏳"}</span>
            <div className="flex-1">
              <h2 className="font-semibold text-navy-800">
                {complete
                  ? "Onboarding complete"
                  : stage === "asking"
                  ? "Bot is asking you questions"
                  : stage === "reviewing"
                  ? "Waiting for your confirmation in Telegram"
                  : stage === "not_started"
                  ? "Onboarding not started"
                  : "Status unknown"}
              </h2>
              <p className="text-sm text-navy-600 mt-1">
                {complete
                  ? "All preference fields are filled. The pipeline is generating matches."
                  : "Open the Telegram bot and reply to the questions. Once you confirm the profile, the pipeline will start matching."}
              </p>
            </div>
          </div>
        </section>

        {profile && (
          <section className="card p-5">
            <h2 className="text-xs uppercase tracking-wider text-navy-500 font-semibold mb-3">Preference fields</h2>
            <div className="space-y-2">
              {ALL_PREFERENCE_FIELDS.map((field) => {
                const value = (profile as unknown as Record<string, unknown>)[field.key];
                const filled =
                  value !== null &&
                  value !== undefined &&
                  (Array.isArray(value) ? value.length > 0 : value !== "");
                return (
                  <div key={field.key} className="flex items-center gap-3 py-2 border-b border-navy-50 last:border-0">
                    <span className="text-xl">{filled ? "✅" : "⬜"}</span>
                    <div className="flex-1">
                      <div className="font-medium text-navy-800">{field.label}</div>
                      <div className="text-xs text-navy-500">
                        {filled
                          ? renderValue(value)
                          : queue.includes(field.key)
                          ? "Bot is asking you right now"
                          : "Not collected yet"}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        <section className="card p-5">
          <h2 className="text-xs uppercase tracking-wider text-navy-500 font-semibold mb-3">How to update your preferences</h2>
          <ol className="space-y-2 text-sm text-navy-700 list-decimal pl-5">
            <li>Open the Telegram bot conversation.</li>
            <li>Send <code className="bg-navy-50 px-1 rounded">/start</code> or your resume PDF if you have not already.</li>
            <li>Reply to each question the bot asks. Use commas to separate list items (e.g. <code>Delhi, Remote, Bangalore</code>).</li>
            <li>When you see the profile review card, tap <strong>✅ Confirm</strong> to save, or <strong>✏️ Edit</strong> to change a field.</li>
          </ol>
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

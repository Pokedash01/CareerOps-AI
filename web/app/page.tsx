import Header from "@/components/Header";
import ScorePill from "@/components/ScorePill";
import { getProfile, getMatchedJobs, getPipelineState, isOnboardingComplete } from "@/lib/github";

export const revalidate = 300;

export default async function DashboardPage() {
  const [profile, jobs, state, complete] = await Promise.all([
    getProfile(),
    getMatchedJobs(),
    getPipelineState(),
    isOnboardingComplete(),
  ]);

  const recent = jobs.slice(0, 5);
  const seenCount = Object.keys(state?.seen_jobs ?? {}).length;

  return (
    <main>
      <Header />
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        <div className="grid grid-cols-3 gap-4">
          <StatCard label="Fit matches" value={jobs.length} icon="🎯" />
          <StatCard label="Listings evaluated" value={seenCount} icon="🔍" />
          <StatCard label="Onboarding" value={complete ? "Complete" : "Pending"} icon={complete ? "✅" : "⏳"} />
        </div>

        {!complete && (
          <div className="card p-4 bg-amber-50 border-amber-200 flex items-start gap-3">
            <span className="text-2xl">⏳</span>
            <div>
              <p className="font-semibold text-navy-800">Onboarding incomplete</p>
              <p className="text-sm text-navy-600 mt-0.5">
                Open the Telegram bot and reply to the preference questions.
              </p>
              <a href="/onboarding" className="text-xs text-amber-700 mt-1 inline-block hover:underline">
                View status →
              </a>
            </div>
          </div>
        )}

        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-navy-800 uppercase tracking-wider">Latest matches</h2>
            {jobs.length > 5 && (
              <a href="/jobs" className="text-xs text-navy-500 hover:text-navy-700">View all ({jobs.length}) →</a>
            )}
          </div>
          {recent.length === 0 ? (
            <div className="card p-8 text-center text-navy-400 text-sm">
              No matches yet. The pipeline runs every 4 hours.
            </div>
          ) : (
            <div className="space-y-3">
              {recent.map((job) => (
                <div key={job.job_id} className="card p-4 flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-navy-800 truncate">{job.title}</span>
                      {job.fit_score !== undefined && <ScorePill score={job.fit_score} />}
                    </div>
                    <p className="text-sm text-navy-500 mt-0.5">{job.company_name} · 📍 {job.location}</p>
                    {job.ats_report && (
                      <p className="text-xs text-navy-400 mt-1">
                        ATS: {job.ats_report.match_score_before}% →{" "}
                        <span className="text-emerald-600">{job.ats_report.match_score_after}%</span>
                      </p>
                    )}
                  </div>
                  <a href={job.apply_link} target="_blank" rel="noreferrer" className="btn-ghost text-xs shrink-0">
                    Apply ↗
                  </a>
                </div>
              ))}
            </div>
          )}
        </section>

        {profile && (
          <section>
            <h2 className="text-sm font-semibold text-navy-800 uppercase tracking-wider mb-3">Your profile</h2>
            <div className="card p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-navy-800">{profile.full_name}</p>
                  <p className="text-sm text-navy-500">{profile.total_years_experience} yrs · {profile.seniority_tier}</p>
                </div>
                <a href="/profile" className="btn-ghost text-xs">Full profile →</a>
              </div>
              <div className="flex flex-wrap gap-1.5 mt-3">
                {profile.skills.slice(0, 10).map((s) => (
                  <span key={s} className="text-xs bg-navy-50 text-navy-600 px-2 py-0.5 rounded">{s}</span>
                ))}
                {profile.skills.length > 10 && (
                  <span className="text-xs text-navy-400">+{profile.skills.length - 10} more</span>
                )}
              </div>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string | number; icon: string }) {
  return (
    <div className="card p-4 flex items-center gap-3">
      <span className="text-2xl">{icon}</span>
      <div>
        <p className="text-2xl font-bold text-navy-900">{value}</p>
        <p className="text-xs text-navy-500">{label}</p>
      </div>
    </div>
  );
}

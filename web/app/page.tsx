import Link from "next/link";
import Header from "@/components/Header";
import {
  Briefcase, Search, Sparkles, ArrowRight, CheckCircle2, Clock,
  MapPin, TrendingUp, FileText, Zap,
} from "lucide-react";
import { getProfile, getMatchedJobs, getPipelineState, isOnboardingComplete } from "@/lib/github";

export const revalidate = 300;

export default async function DashboardPage() {
  const [profile, jobs, state, complete] = await Promise.all([
    getProfile(),
    getMatchedJobs(),
    getPipelineState(),
    isOnboardingComplete(),
  ]);

  const seenCount = Object.keys(state?.seen_jobs ?? {}).length;
  const highFit = jobs.filter((j) => (j.fit_score ?? 0) >= 70).length;
  const lastJob = jobs[jobs.length - 1];
  const lastRunTime = state?.seen_jobs
    ? Object.values(state.seen_jobs).sort().reverse()[0]?.split("T")[0] ?? "—"
    : "—";

  return (
    <main>
      <Header />
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Hero */}
        <section className="card hero-blur">
          <div className="relative z-10 flex items-start justify-between gap-6 flex-wrap">
            <div>
              <h1 className="text-2xl font-bold text-white">
                {profile?.full_name ? `Welcome back, ${profile.full_name.split(" ")[0]}` : "Welcome to CareerOps"}
              </h1>
              <p className="text-sm text-gray-400 mt-1.5 max-w-xl">
                Your AI-driven pipeline. {complete
                  ? "All preferences set — matches are being generated every 4 hours."
                  : "Complete onboarding to start receiving matched roles."}
              </p>
            </div>
            <Link href={complete ? "/jobs" : "/onboarding"} className="btn-primary">
              {complete ? "View matches" : "Finish onboarding"} <ArrowRight size={14} />
            </Link>
          </div>
        </section>

        {/* Workflow status strip */}
        <section className="sub-card px-5 py-3 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-xs">
            <Clock size={14} className="text-gray-500" />
            <span className="text-gray-500">Cadence:</span>
            <span className="text-white font-medium">Every 4h</span>
          </div>
          <div className="w-px h-4 bg-[#1F2937]" />
          <div className="flex items-center gap-2 text-xs">
            <CheckCircle2 size={14} className={complete ? "text-emerald-500" : "text-amber-500"} />
            <span className="text-gray-500">Onboarding:</span>
            <span className={complete ? "text-emerald-400" : "text-amber-400"}>
              {complete ? "Complete" : "Pending"}
            </span>
          </div>
          <div className="w-px h-4 bg-[#1F2937]" />
          <div className="flex items-center gap-2 text-xs">
            <Zap size={14} className="text-blue-500" />
            <span className="text-gray-500">Last run:</span>
            <span className="text-white font-medium">{lastRunTime}</span>
          </div>
          <div className="ml-auto text-xs text-gray-500">
            Next sync in <span className="text-white font-mono">~3h 42m</span>
          </div>
        </section>

        {/* Metrics grid */}
        <section className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <MetricCard label="Total matches" value={jobs.length} icon={Briefcase} color="blue" caption="Notified roles" />
          <MetricCard label="High-fit" value={highFit} icon={TrendingUp} color="emerald" caption="Score ≥ 70%" />
          <MetricCard label="Evaluated" value={seenCount} icon={Search} color="indigo" caption="Listings scanned" />
          <MetricCard label="Onboarding" value={complete ? "Done" : "Pending"} icon={Sparkles} color="purple" caption={complete ? "Ready" : "Action needed"} isText />
          <MetricCard label="Last match" value={lastJob ? lastJob.title.split(" ").slice(0, 2).join(" ") : "—"} icon={FileText} color="amber" caption={lastJob ? lastJob.company_name : "No matches yet"} isText />
        </section>

        {/* Two-column: Profile + Latest matches */}
        <section className="grid lg:grid-cols-3 gap-6">
          {/* Profile snapshot */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Profile</h2>
              <Link href="/profile" className="text-xs text-blue-400 hover:text-blue-300">Edit →</Link>
            </div>
            {profile ? (
              <div className="space-y-4">
                <div>
                  <p className="text-base font-semibold text-white">{profile.full_name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {profile.total_years_experience} years · {profile.seniority_tier}
                  </p>
                </div>
                <div>
                  <p className="label mb-2">Skills</p>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.skills.slice(0, 10).map((s) => (
                      <span key={s} className="chip-neutral">{s}</span>
                    ))}
                    {profile.skills.length > 10 && (
                      <span className="text-xs text-gray-500 self-center">+{profile.skills.length - 10}</span>
                    )}
                  </div>
                </div>
                {profile.preferred_locations?.length > 0 && (
                  <div>
                    <p className="label mb-2">Locations</p>
                    <div className="flex flex-wrap gap-1.5">
                      {profile.preferred_locations.map((l) => <span key={l} className="chip-blue">{l}</span>)}
                    </div>
                  </div>
                )}
                {profile.target_roles?.length > 0 && (
                  <div>
                    <p className="label mb-2">Target roles</p>
                    <div className="flex flex-wrap gap-1.5">
                      {profile.target_roles.map((r) => <span key={r} className="chip-emerald">{r}</span>)}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No profile yet. Upload your resume via Telegram.</p>
            )}
          </div>

          {/* Latest matches */}
          <div className="lg:col-span-2 card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Latest matches</h2>
              {jobs.length > 0 && (
                <Link href="/jobs" className="text-xs text-blue-400 hover:text-blue-300">
                  View all ({jobs.length}) →
                </Link>
              )}
            </div>
            {jobs.length === 0 ? (
              <div className="sub-card p-8 text-center">
                <Briefcase size={32} className="mx-auto text-gray-600 mb-3" />
                <p className="text-sm text-gray-400">No matches yet</p>
                <p className="text-xs text-gray-600 mt-1">Pipeline runs every 4 hours.</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto pr-2">
                {jobs.slice().reverse().slice(0, 5).map((job) => (
                  <Link
                    key={job.job_id}
                    href={`/jobs`}
                    className="sub-card p-4 block hover:border-blue-500/40 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-white truncate">{job.title}</p>
                          {job.fit_score !== undefined && (
                            <span className={job.fit_score >= 70 ? "chip-emerald" : job.fit_score >= 40 ? "chip-amber" : "chip-rose"}>
                              {job.fit_score}%
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-400 mt-1 flex items-center gap-3">
                          <span>{job.company_name}</span>
                          <span className="flex items-center gap-1"><MapPin size={11} />{job.location}</span>
                        </p>
                        {job.ats_report && (
                          <p className="text-xs text-gray-500 mt-1.5">
                            ATS: {job.ats_report.match_score_before}% → <span className="text-emerald-400">{job.ats_report.match_score_after}%</span>
                          </p>
                        )}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

const ICON_COLORS = {
  blue: "bg-blue-500/10 text-blue-400",
  emerald: "bg-emerald-500/10 text-emerald-400",
  indigo: "bg-indigo-500/10 text-indigo-400",
  purple: "bg-purple-500/10 text-purple-400",
  amber: "bg-amber-500/10 text-amber-400",
} as const;

function MetricCard({
  label, value, icon: Icon, color, caption, isText,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  color: keyof typeof ICON_COLORS;
  caption: string;
  isText?: boolean;
}) {
  return (
    <div className="card !p-5">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="label">{label}</p>
          <p className={`mt-2 font-bold text-white ${isText ? "text-lg" : "text-3xl"}`}>
            {value}
          </p>
          <p className="text-xs text-gray-500 mt-1">{caption}</p>
        </div>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${ICON_COLORS[color]}`}>
          <Icon size={18} />
        </div>
      </div>
    </div>
  );
}

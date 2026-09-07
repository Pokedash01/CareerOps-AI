import Header from "@/components/Header";
import ScorePill from "@/components/ScorePill";
import GenerateButton from "./GenerateButton";
import { getMatchedJobs, getProfile } from "@/lib/github";
import { JobMatch } from "@/lib/types";

export const revalidate = 300;

export default async function JobsPage() {
  const [jobs, profile] = await Promise.all([getMatchedJobs(), getProfile()]);

  if (!profile) {
    return (
      <main>
        <Header />
        <div className="max-w-4xl mx-auto px-6 py-12">
          <div className="card p-8 text-center text-navy-500">
            No profile found. Upload your resume via the Telegram bot first.
          </div>
        </div>
      </main>
    );
  }

  if (jobs.length === 0) {
    return (
      <main>
        <Header />
        <div className="max-w-4xl mx-auto px-6 py-12">
          <h1 className="text-xl font-semibold text-navy-800 mb-6">Jobs</h1>
          <div className="card p-8 text-center text-navy-500">
            No matched jobs yet. The pipeline runs every 4 hours — new matches will appear here shortly.
          </div>
        </div>
      </main>
    );
  }

  return (
    <main>
      <Header />
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-navy-800">
            Matched Jobs
            <span className="ml-2 text-sm font-normal text-navy-500">({jobs.length} total)</span>
          </h1>
          <span className="text-xs text-navy-500">Data refreshes every 5 min · Pipeline runs every 4h</span>
        </div>
        <div className="space-y-3">
          {jobs.map((job) => <JobCard key={job.job_id} job={job} />)}
        </div>
      </div>
    </main>
  );
}

function JobCard({ job }: { job: JobMatch }) {
  const score = job.fit_score ?? 0;

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="font-semibold text-navy-800">{job.title}</h2>
            <ScorePill score={score} />
          </div>
          <p className="text-sm text-navy-600 mt-0.5">{job.company_name} · 📍 {job.location}</p>

          {job.ats_report && (
            <div className="mt-3 space-y-2">
              <div>
                <span className="text-xs font-medium text-emerald-600">✅ Matched:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {job.ats_report.matched_keywords.slice(0, 6).map((kw) => (
                    <span key={kw} className="text-xs bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded">{kw}</span>
                  ))}
                </div>
              </div>
              <div>
                <span className="text-xs font-medium text-amber-600">⚠️ Missing:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {job.ats_report.missing_keywords.slice(0, 6).map((kw) => (
                    <span key={kw} className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded">{kw}</span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {job.ats_report && (
            <div className="mt-2 flex gap-4 text-xs text-navy-500">
              <span>Before: <strong className="text-navy-700">{job.ats_report.match_score_before}%</strong></span>
              <span>After: <strong className="text-emerald-600">{job.ats_report.match_score_after}%</strong></span>
              {job.ats_report.score_delta > 0 && (
                <span className="text-emerald-600">+{job.ats_report.score_delta} pts</span>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2 items-end shrink-0">
          <GenerateButton jobId={job.job_id} jobTitle={job.title} company={job.company_name} />
          <a href={job.apply_link} target="_blank" rel="noreferrer" className="btn-ghost text-xs">Apply ↗</a>
        </div>
      </div>
    </div>
  );
}

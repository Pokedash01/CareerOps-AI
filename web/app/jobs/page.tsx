import Link from "next/link";
import Header from "@/components/Header";
import {
  MapPin, TrendingUp, TrendingDown, Building2, CheckCircle2, AlertCircle,
  Briefcase, Sparkles,
} from "lucide-react";
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
        <div className="max-w-7xl mx-auto px-6 py-12">
          <div className="card text-center text-gray-400">
            No profile found. Upload your resume via the Telegram bot first.
          </div>
        </div>
      </main>
    );
  }

  return (
    <main>
      <Header />
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        <div className="flex items-end justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-white">Matched Jobs</h1>
            <p className="text-sm text-gray-400 mt-1">
              {jobs.length} {jobs.length === 1 ? "role" : "roles"} matched against your profile
            </p>
          </div>
          <span className="text-xs text-gray-500">
            Data refreshes every 5 min · Pipeline runs every 4h
          </span>
        </div>

        {jobs.length === 0 ? (
          <div className="card text-center py-16">
            <Briefcase size={36} className="mx-auto text-gray-600 mb-3" />
            <p className="text-sm text-gray-400">No matched jobs yet</p>
            <p className="text-xs text-gray-600 mt-1">The pipeline runs every 4 hours — new matches will appear here shortly.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {jobs.map((job) => <JobCard key={job.job_id} job={job} />)}
          </div>
        )}
      </div>
    </main>
  );
}

function JobCard({ job }: { job: JobMatch }) {
  const score = job.fit_score ?? 0;
  const scoreClass = score >= 70 ? "chip-emerald" : score >= 40 ? "chip-amber" : "chip-rose";

  return (
    <div className="card hover:border-blue-500/40 transition-colors">
      <div className="flex items-start justify-between gap-6 flex-wrap">
        <div className="flex-1 min-w-0 space-y-3">
          {/* Title + score */}
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-lg font-semibold text-white">{job.title}</h2>
            <span className={scoreClass}>{score}% match</span>
            {job.is_viable === false && (
              <span className="chip-rose">Not viable</span>
            )}
          </div>

          {/* Company + location */}
          <div className="flex items-center gap-4 text-sm text-gray-400 flex-wrap">
            <span className="flex items-center gap-1.5"><Building2 size={13} />{job.company_name}</span>
            <span className="flex items-center gap-1.5"><MapPin size={13} />{job.location}</span>
            {job.salary_range && (
              <span className="flex items-center gap-1.5 text-emerald-400">💰 {job.salary_range}</span>
            )}
            {job.detected_experience && job.detected_experience !== "Not specified in JD" && (
              <span className="flex items-center gap-1.5">⏳ {job.detected_experience}</span>
            )}
          </div>

          {/* ATS keywords */}
          {job.ats_report && (
            <div className="grid sm:grid-cols-2 gap-4 pt-2">
              <div>
                <p className="label flex items-center gap-1.5 mb-2">
                  <CheckCircle2 size={11} className="text-emerald-500" /> Matched keywords
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {job.ats_report.matched_keywords.slice(0, 8).map((kw) => (
                    <span key={kw} className="chip-emerald">{kw}</span>
                  ))}
                </div>
              </div>
              <div>
                <p className="label flex items-center gap-1.5 mb-2">
                  <AlertCircle size={11} className="text-amber-500" /> Missing keywords
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {job.ats_report.missing_keywords.slice(0, 8).map((kw) => (
                    <span key={kw} className="chip-amber">{kw}</span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ATS score */}
          {job.ats_report && (
            <div className="sub-card p-3 flex items-center gap-6 text-xs">
              <div className="flex items-center gap-1.5">
                <span className="text-gray-500">Before:</span>
                <span className="text-white font-semibold">{job.ats_report.match_score_before}%</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-gray-500">After tailoring:</span>
                <span className="text-emerald-400 font-semibold">{job.ats_report.match_score_after}%</span>
              </div>
              {job.ats_report.score_delta > 0 ? (
                <div className="flex items-center gap-1 text-emerald-400">
                  <TrendingUp size={12} /> +{job.ats_report.score_delta} pts
                </div>
              ) : job.ats_report.score_delta < 0 ? (
                <div className="flex items-center gap-1 text-rose-400">
                  <TrendingDown size={12} /> {job.ats_report.score_delta} pts
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-2 items-end shrink-0 min-w-[180px]">
          <GenerateButton jobId={job.job_id} jobTitle={job.title} company={job.company_name} />
          <a href={job.apply_link} target="_blank" rel="noreferrer" className="btn-secondary w-full justify-center">
            Apply ↗
          </a>
        </div>
      </div>
    </div>
  );
}

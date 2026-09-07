import Link from "next/link";
import { Mail, Phone, MapPin, Briefcase, GraduationCap, Award, Settings } from "lucide-react";
import Header from "@/components/Header";
import { getProfile } from "@/lib/github";

export const revalidate = 300;

export default async function ProfilePage() {
  const profile = await getProfile();

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
        {/* Header card */}
        <div className="card">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-white">{profile.full_name}</h1>
              <p className="text-sm text-gray-400 mt-1">
                {profile.total_years_experience} years · {profile.seniority_tier}
              </p>
              <div className="flex flex-wrap gap-4 mt-3 text-sm text-gray-400">
                {profile.contact?.email && (
                  <span className="flex items-center gap-1.5"><Mail size={13} />{profile.contact.email}</span>
                )}
                {profile.contact?.phone && (
                  <span className="flex items-center gap-1.5"><Phone size={13} />{profile.contact.phone}</span>
                )}
                {profile.contact?.location && (
                  <span className="flex items-center gap-1.5"><MapPin size={13} />{profile.contact.location}</span>
                )}
              </div>
            </div>
            <Link href="/settings" className="btn-secondary">
              <Settings size={14} /> Edit preferences
            </Link>
          </div>
        </div>

        {/* Skills */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Award size={16} className="text-blue-400" />
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Skills</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {profile.skills.map((s) => (
              <span key={s} className="chip-blue">{s}</span>
            ))}
          </div>
          {profile.certifications?.length > 0 && (
            <>
              <p className="label mt-6 mb-3">Certifications</p>
              <div className="flex flex-wrap gap-2">
                {profile.certifications.map((c) => (
                  <span key={c} className="chip-emerald">{c}</span>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Experience */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Briefcase size={16} className="text-blue-400" />
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Work Experience</h2>
          </div>
          <div className="space-y-5">
            {profile.experience.map((exp, i) => (
              <div
                key={i}
                className={`sub-card p-4 ${i < profile.experience.length - 1 ? "" : ""}`}
              >
                <div className="flex items-start justify-between flex-wrap gap-2">
                  <div>
                    <p className="text-base font-semibold text-white">{exp.role}</p>
                    <p className="text-sm text-gray-400 mt-0.5">
                      {exp.company}{exp.location ? ` · ${exp.location}` : ""}
                    </p>
                  </div>
                  {exp.dates && <span className="text-xs text-gray-500">{exp.dates}</span>}
                </div>
                {exp.summary && <p className="text-sm text-gray-300 mt-3">{exp.summary}</p>}
                {exp.bullets.length > 0 && (
                  <ul className="mt-3 space-y-1.5">
                    {exp.bullets.map((b, j) => (
                      <li key={j} className="text-sm text-gray-300 pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-gray-600">
                        {b}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Education */}
        {profile.education?.length > 0 && (
          <div className="card">
            <div className="flex items-center gap-2 mb-4">
              <GraduationCap size={16} className="text-blue-400" />
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Education</h2>
            </div>
            <div className="space-y-3">
              {profile.education.map((edu, i) => (
                <div key={i} className="sub-card p-4">
                  <p className="text-sm font-semibold text-white">{edu.institution}</p>
                  <p className="text-sm text-gray-400 mt-1">
                    {edu.degree}{edu.details ? ` · ${edu.details}` : ""}
                  </p>
                  {edu.dates && <p className="text-xs text-gray-500 mt-1">{edu.dates}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Preferences */}
        <div className="card">
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Preferences</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <PrefItem label="Locations" value={profile.preferred_locations?.join(", ")} />
            <PrefItem label="Target roles" value={profile.target_roles?.join(", ")} />
            <PrefItem label="Avoiding" value={profile.anti_targets?.join(", ") || "None"} />
            <PrefItem label="Internships" value={profile.open_to_internship ? "Yes" : "No"} />
            {profile.salary_expectation && (
              <PrefItem
                label="Salary"
                value={`₹${profile.salary_expectation.min_lpa ?? "?"} – ₹${profile.salary_expectation.max_lpa ?? "?"} LPA`}
              />
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

function PrefItem({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="sub-card p-4">
      <p className="label mb-1.5">{label}</p>
      <p className="text-sm text-white">{value || "—"}</p>
    </div>
  );
}

import Header from "@/components/Header";
import { getProfile } from "@/lib/github";

export const revalidate = 300;

export default async function ProfilePage() {
  const profile = await getProfile();

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

  return (
    <main>
      <Header />
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        <div className="card p-6">
          <h1 className="text-xl font-bold text-navy-900">{profile.full_name}</h1>
          <p className="text-navy-600 mt-1">{profile.total_years_experience} years · {profile.seniority_tier}</p>
          <div className="flex flex-wrap gap-4 mt-3 text-sm text-navy-500">
            {profile.contact?.email && <span>📧 {profile.contact.email}</span>}
            {profile.contact?.phone && <span>📱 {profile.contact.phone}</span>}
            {profile.contact?.location && <span>📍 {profile.contact.location}</span>}
          </div>
        </div>

        <section className="card p-5">
          <h2 className="text-xs uppercase tracking-wider text-navy-500 font-semibold mb-3">Skills</h2>
          <div className="flex flex-wrap gap-2">
            {profile.skills.map((s) => (
              <span key={s} className="text-sm bg-navy-50 text-navy-700 px-3 py-1 rounded-full">{s}</span>
            ))}
          </div>
          {profile.certifications?.length > 0 && (
            <>
              <h3 className="text-xs uppercase tracking-wider text-navy-500 font-semibold mt-5 mb-2">Certifications</h3>
              <div className="flex flex-wrap gap-2">
                {profile.certifications.map((c) => (
                  <span key={c} className="text-sm bg-emerald-50 text-emerald-700 px-3 py-1 rounded-full">{c}</span>
                ))}
              </div>
            </>
          )}
        </section>

        <section className="card p-5">
          <h2 className="text-xs uppercase tracking-wider text-navy-500 font-semibold mb-4">Work Experience</h2>
          <div className="space-y-5">
            {profile.experience.map((exp, i) => (
              <div key={i} className={i < profile.experience.length - 1 ? "border-b border-navy-50 pb-5" : ""}>
                <div>
                  <p className="font-semibold text-navy-800">{exp.role}</p>
                  <p className="text-sm text-navy-600">
                    {exp.company}{exp.location ? ` · ${exp.location}` : ""}
                  </p>
                  {exp.dates && <p className="text-xs text-navy-400 mt-0.5">{exp.dates}</p>}
                </div>
                {exp.summary && <p className="text-sm text-navy-600 mt-2">{exp.summary}</p>}
                {exp.bullets.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {exp.bullets.map((b, j) => (
                      <li key={j} className="text-sm text-navy-700 pl-4 relative before:content-['•'] before:absolute before:-left-1 before:text-navy-400">
                        {b}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </section>

        {profile.education?.length > 0 && (
          <section className="card p-5">
            <h2 className="text-xs uppercase tracking-wider text-navy-500 font-semibold mb-3">Education</h2>
            <div className="space-y-3">
              {profile.education.map((edu, i) => (
                <div key={i}>
                  <p className="font-medium text-navy-800">{edu.institution}</p>
                  <p className="text-sm text-navy-600">{edu.degree}{edu.details ? ` · ${edu.details}` : ""}</p>
                  {edu.dates && <p className="text-xs text-navy-400 mt-0.5">{edu.dates}</p>}
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="card p-5">
          <h2 className="text-xs uppercase tracking-wider text-navy-500 font-semibold mb-3">Preferences</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <PreferenceItem label="Locations" value={profile.preferred_locations?.join(", ")} />
            <PreferenceItem label="Target roles" value={profile.target_roles?.join(", ")} />
            <PreferenceItem label="Avoiding" value={profile.anti_targets?.join(", ") || "None"} />
            <PreferenceItem label="Internships" value={profile.open_to_internship ? "Yes" : "No"} />
            {profile.salary_expectation && (
              <PreferenceItem
                label="Salary"
                value={`₹${profile.salary_expectation.min_lpa ?? "?"} – ₹${profile.salary_expectation.max_lpa ?? "?"} LPA`}
              />
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function PreferenceItem({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <p className="text-xs text-navy-400 uppercase tracking-wider">{label}</p>
      <p className="text-navy-800 mt-0.5">{value || "—"}</p>
    </div>
  );
}

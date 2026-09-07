// Shared TypeScript types matching the shape written by the bot's
// profiler.py and matcher.py.

export interface Contact {
  email?: string;
  phone?: string;
  location?: string;
  links?: string;
}

export interface Education {
  institution: string;
  degree: string;
  details: string;
  dates: string;
}

export interface Experience {
  company: string;
  role: string;
  location?: string;
  dates?: string;
  summary?: string;
  bullets: string[];
}

export interface ATSReport {
  match_score_before: number;
  match_score_after: number;
  score_delta: number;
  jd_keywords: string[];
  matched_keywords: string[];
  missing_keywords: string[];
  keyword_coverage_pct: number;
  format_issues: string[];
  suggestions: string[];
}

export interface Profile {
  full_name: string;
  contact: Contact;
  total_years_experience: number;
  seniority_tier: string;
  education: Education[];
  experience: Experience[];
  skills: string[];
  certifications: string[];
  target_roles: string[];
  anti_targets: string[];
  preferred_locations: string[];
  salary_expectation?: { min_lpa?: number; max_lpa?: number } | null;
  salary_expectation_min_lpa?: number | null;
  salary_expectation_max_lpa?: number | null;
  open_to_internship: boolean;
  open_to_training_programs: boolean;
}

export interface JobMatch {
  job_id: string;
  title: string;
  company_name: string;
  description: string;
  apply_link: string;
  location: string;
  salary_range_lpa?: [number, number] | null;
  experience_range_years?: [number, number] | null;
  used_full_jd: boolean;
  fit_score?: number;
  is_viable?: boolean;
  rejection_reason?: string;
  detected_experience?: string;
  salary_range?: string;
  skills_gap?: string;
  ats_report?: ATSReport;
  notified?: boolean;
  seen?: boolean;
}

export interface OnboardingState {
  stage: "asking" | "reviewing" | "done";
  queue: string[];
  answers: Record<string, unknown>;
  message_id: number | null;
  editing_field: string | null;
  last_seen_update: string;
}

export interface PipelineState {
  telegram_offset: number | null;
  seen_jobs: Record<string, string>;
  notified_jobs: string[];
  onboarding: Record<string, OnboardingState>;
}

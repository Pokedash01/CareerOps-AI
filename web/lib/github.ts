/**
 * GitHub data fetching layer.
 * All data is read from the public raw.githubusercontent.com CDN so
 * no credentials are needed to browse the dashboard.
 */

import { Profile, JobMatch, PipelineState } from "./types";

const GITHUB_REPO = process.env.GITHUB_REPO || "Pokedash01/CareerOps-AI";
const [OWNER, REPO] = GITHUB_REPO.split("/");

const CHAT_ID = process.env.DASHBOARD_CHAT_ID || "1368681854";

async function fetchJSON<T>(path: string): Promise<T | null> {
  const url = `https://raw.githubusercontent.com/${OWNER}/${REPO}/main/${path}`;
  try {
    const res = await fetch(url, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return res.json() as Promise<T>;
  } catch {
    return null;
  }
}

export async function getProfile(): Promise<Profile | null> {
  return fetchJSON<Profile>(`data/users/${CHAT_ID}/profile.json`);
}

export async function getMatchedJobs(): Promise<JobMatch[]> {
  const jobs = await fetchJSON<JobMatch[]>(`data/users/${CHAT_ID}/jobs.json`);
  return jobs ?? [];
}

export async function getPipelineState(): Promise<PipelineState | null> {
  return fetchJSON<PipelineState>("data/state.json");
}

export async function isOnboardingComplete(): Promise<boolean> {
  const state = await getPipelineState();
  if (!state) return false;
  const ob = state.onboarding?.[CHAT_ID];
  return ob?.stage === "done";
}

export async function getOnboardingQueue(): Promise<string[]> {
  const state = await getPipelineState();
  if (!state) return [];
  const ob = state.onboarding?.[CHAT_ID];
  return ob?.queue ?? [];
}

export { CHAT_ID, OWNER, REPO, GITHUB_REPO };

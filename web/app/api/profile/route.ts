import { NextRequest, NextResponse } from "next/server";
import { Octokit } from "@octokit/rest";

export async function POST(req: NextRequest) {
  const githubToken = process.env.GITHUB_TOKEN;
  const chatId = process.env.DASHBOARD_CHAT_ID || "1368681854";
  const repo = process.env.GITHUB_REPO || "Pokedash01/CareerOps-AI";
  const [owner, repoName] = repo.split("/");

  if (!githubToken) {
    return NextResponse.json({ error: "GITHUB_TOKEN not configured" }, { status: 500 });
  }

  const body = await req.json();

  try {
    const octokit = new Octokit({ auth: githubToken });

    // 1. Read existing profile.json from GitHub
    let existingProfile: Record<string, unknown> = {};
    try {
      const { data } = await octokit.repos.getContent({
        owner, repo: repoName, path: `data/users/${chatId}/profile.json`, branch: "main",
      });
      if (data && data.encoding === "base64") {
        existingProfile = JSON.parse(Buffer.from((data as { content: string }).content, "base64").toString("utf-8"));
      }
    } catch {
      // File doesn't exist yet — that's fine, we create it
    }

    // 2. Merge in the updated fields
    const updatedProfile = { ...existingProfile, ...body };

    // 3. Write profile.json back to GitHub
    const content = Buffer.from(JSON.stringify(updatedProfile, null, 2)).toString("base64");
    const filePath = `data/users/${chatId}/profile.json`;

    try {
      await octokit.repos.createOrUpdateFileContents({
        owner, repo: repoName, path: filePath,
        message: `chore: update profile preferences via dashboard`,
        content,
        branch: "main",
      });
    } catch (e) {
      // If file didn't exist, create it
      await octokit.repos.createOrUpdateFileContents({
        owner, repo: repoName,
        path: filePath,
        message: `chore: create profile via dashboard`,
        content,
        branch: "main",
      });
    }

    // 4. Mark those fields as answered in onboarding state
    // Read state.json, remove the answered fields from onboarding queue, mark stage=done
    let stateContent: Record<string, unknown> = {};
    try {
      const { data } = await octokit.repos.getContent({
        owner, repo: repoName, path: "data/state.json", branch: "main",
      });
      if (data && data.encoding === "base64") {
        stateContent = JSON.parse(Buffer.from((data as { content: string }).content, "base64").toString("utf-8"));
      }
    } catch {
      // state.json doesn't exist — create basic structure
      stateContent = { telegram_offset: null, seen_jobs: {}, notified_jobs: [], onboarding: {} };
    }

    const onboarding = stateContent.onboarding as Record<string, Record<string, unknown>> || {};
    const userOnb = onboarding[chatId] || {};

    if (userOnb.queue && Array.isArray(userOnb.queue)) {
      // Remove the fields that were just saved
      const savedFields = Object.keys(body);
      userOnb.queue = (userOnb.queue as string[]).filter(f => !savedFields.includes(f));
    }

    // If queue is empty and we just saved real data, mark onboarding as done
    const queue = (userOnb.queue as string[]) || [];
    if (queue.length === 0) {
      userOnb.stage = "done";
      userOnb.queue = [];
    }

    onboarding[chatId] = userOnb;
    stateContent.onboarding = onboarding;

    const stateEncoded = Buffer.from(JSON.stringify(stateContent, null, 2)).toString("base64");
    try {
      await octokit.repos.createOrUpdateFileContents({
        owner, repo: repoName, path: "data/state.json",
        message: "chore: update onboarding state via dashboard",
        content: stateEncoded, branch: "main",
      });
    } catch {
      // state.json may not exist — try to create
      await octokit.repos.createOrUpdateFileContents({
        owner, repo: repoName, path: "data/state.json",
        message: "chore: create state.json via dashboard",
        content: stateEncoded, branch: "main",
      });
    }

    return NextResponse.json({ ok: true, profile: updatedProfile, onboardingStage: userOnb.stage });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

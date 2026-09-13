import { NextRequest, NextResponse } from "next/server";
import { Octokit } from "@octokit/rest";

export const runtime = "nodejs";
export const maxDuration = 15;

export async function POST(req: NextRequest) {
  const githubToken = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO || "Pokedash01/CareerOps-AI";
  const [owner, repoName] = repo.split("/");

  if (!githubToken) {
    return NextResponse.json({ error: "GITHUB_TOKEN not configured" }, { status: 500 });
  }

  try {
    const octokit = new Octokit({ auth: githubToken });

    const { ref } = await req.json();
    const workflowRef = ref || "careerops.yml";

    await octokit.rest.actions.createWorkflowDispatch({
      owner,
      repo: repoName,
      workflow_id: workflowRef,
      ref: "main",
      inputs: {},
    });

    return NextResponse.json({ ok: true, message: `Pipeline triggered for ${workflowRef}` });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

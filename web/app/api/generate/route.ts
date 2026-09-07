import { NextRequest, NextResponse } from "next/server";
import { spawnSync } from "child_process";
import { Octokit } from "@octokit/rest";

const PYTHON = process.env.PYTHON_PATH || "python3";

export const runtime = "nodejs";
export const maxDuration = 90;

export async function POST(req: NextRequest) {
  const { jobId, jobTitle, company } = await req.json();

  const githubToken = process.env.GITHUB_TOKEN;
  const chatId = process.env.DASHBOARD_CHAT_ID || "1368681854";
  const repo = process.env.GITHUB_REPO || "Pokedash01/CareerOps-AI";
  const [owner, repoName] = repo.split("/");
  const scriptPath = require("path").join(process.cwd(), "scripts/generate.py");

  if (!githubToken) {
    return NextResponse.json({ error: "GITHUB_TOKEN not configured" }, { status: 500 });
  }

  try {
    const result = spawnSync(
      PYTHON,
      [scriptPath, JSON.stringify({ jobId, jobTitle, company })],
      { timeout: 85_000, maxBuffer: 50 * 1024 * 1024 }
    );

    const stdout = result.stdout?.toString()?.trim();
    if (!stdout) {
      return NextResponse.json({ error: result.stderr?.toString() || "No output from generator" }, { status: 500 });
    }

    let parsed: { url?: string; filename?: string; b64?: string };
    try {
      parsed = JSON.parse(stdout);
    } catch {
      return NextResponse.json({ error: "Invalid generator output: " + stdout.slice(0, 200) }, { status: 500 });
    }

    const { b64, filename } = parsed;
    const safeFilename = filename || `Resume_${company}_${jobId}.pdf`;
    const filePath = `data/users/${chatId}/outputs/${jobId}/${safeFilename}`;

    if (b64) {
      const octokit = new Octokit({ auth: githubToken });
      const pdfBuffer = Buffer.from(b64, "base64");
      await octokit.repos.createOrUpdateFileContents({
        owner,
        repo: repoName,
        path: filePath,
        message: `feat: Add tailored resume for ${company}`,
        content: pdfBuffer.toString("base64"),
        branch: "main",
      });
    }

    const rawUrl = `https://raw.githubusercontent.com/${owner}/${repoName}/main/${filePath}`;
    return NextResponse.json({ url: rawUrl, filename: safeFilename });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

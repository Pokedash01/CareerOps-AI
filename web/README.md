# CareerOps AI — Web Dashboard

A companion dashboard for the CareerOps-AI Telegram bot. Read-only view of matched jobs, parsed profiles, and on-demand tailored resume generation.

Built with **Next.js 14** (App Router), **Tailwind CSS**, and deployed on **Vercel**.

## Setup

### 1. Connect repo to Vercel

Link this repo to Vercel. The root `vercel.json` handles the monorepo build (`cd web && npm install && npm run build`).

### 2. Environment variables (Vercel → Settings → Environment Variables)

| Name | Notes |
|---|---|
| `NEXT_PUBLIC_DASHBOARD_PASSWORD` | Shown to visitors before they can see data |
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope |
| `GEMINI_API_KEY` | For on-demand resume tailoring |
| `GROQ_API_KEY` | Fallback LLM |
| `GITHUB_REPO` | `Pokedash01/CareerOps-AI` |
| `DASHBOARD_CHAT_ID` | Your Telegram chat ID |
| `PYTHON_PATH` | `python3` |

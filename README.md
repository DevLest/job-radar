# Job Radar

A personal job-search pipeline with a local web app. It collects jobs from free job feeds **and** from your LinkedIn / Indeed / JobStreet / OnlineJobs.ph alert emails. It filters them for free against your pay, work type and skills, and has Claude score only what's left. It also drafts applications from your CV and tracks every application, including replies in your inbox.

```
 COLLECT                     FILTER (free)                 SCORE (Claude)          APPLY & TRACK
 10 job sites, ATS boards ─► dedupe, work type, cities, ─► 1 small call/job ─────► draft from CV → you review → send / mark applied
 alert emails (IMAP) ──────► pay (with FX), title, age     cached profile prompt    inbox scan for replies → status auto-updates
 jobs you paste in ────────►                               strict JSON output       closed-posting check, follow-up reminders
```

## Start

Double-click **`start.bat`**. It sets itself up the first time, then opens **http://127.0.0.1:5000**. Keep the black window open while you use the app.

The **Home** page has a setup checklist:

1. **Settings**: paste your Anthropic API key. To use email, add your address and a Gmail **App password** (myaccount.google.com/apppasswords), not your normal password.
2. **My CV**: drag your CV in. The AI shows your skills, strengths, gaps and CV tips. Click **Use it** to fill in your preferences.
3. **Preferences**: "I want at least ___ per ___", the ways of working you accept (Remote / Hybrid / On-site cards), the cities where hybrid or on-site is OK, and your skills (type a skill and press Enter).
4. On **LinkedIn, Indeed, JobStreet and OnlineJobs.ph**, create job alerts sent to that email address.
5. Click **Find jobs** (top right) and choose what to check. A progress card shows each step and tells you how many new matches it found.

## Using it

- **Jobs**: tabs for *Top matches*, *Worth a look*, *Not rated yet*, *Filtered out* and *Hidden*. Each card shows a score ring, the work type, the pay, whether the pay and setup fit you, and your matching skills. Search filters as you type. **Hide** removes a job, with Undo. **Rate this job** rates a single job. **More → Add a job I found** takes a job from anywhere.
- **A job's page**: a plain-language explanation of the score (skills, pay, work setup, level) and a 3-step apply panel:
  1. **Write it for me**: the AI drafts from your CV and never invents experience.
  2. Edit the draft.
  3. **Send email** (your CV is attached, and nothing is sent until you click) or **I've applied** for LinkedIn Easy Apply, JobStreet and company sites. The app doesn't auto-submit on those sites: it breaks their terms and gets accounts banned.
- It warns you if you already applied **to this role or at this company**.

## Application tracking

The **Applications** page is a board (Drafts → Applied → Heard back → Interview → Offer → Closed). **Drag a card** to change its status, or use the dropdown on the card. Each application page has a clickable status track, next step, notes and a full history.

**Check application updates** (manual button, or automatic) does three things:

- Finds replies in your inbox. A reply to an email you sent from the app is matched exactly, for free. Other emails that mention the company, arrived after you applied and haven't been seen before are classified by Claude as interview, rejection, request for info, and so on. Statuses only move forward automatically. Each email is sent to Claude at most once.
- Flags postings that went offline (HTTP 404/410) for company-board and remote-feed jobs.
- Adds a "consider a follow-up" reminder after 14 days of silence.

**Automation** (Preferences → AI & automation): while the app is open, it runs your chosen tasks every N hours. Scoring is off by default so it never spends tokens without you choosing that. For runs without the UI, use Task Scheduler:

```powershell
schtasks /create /tn JobRadar /sc daily /st 08:00 /tr "D:\PROGRAMS\laragon\www\job-radar\.venv\Scripts\python.exe D:\PROGRAMS\laragon\www\job-radar\run.py --batch --wait 90"
```

## Cost

| What | Claude calls | Approx. cost (Opus 5.5 / Haiku 4.5) |
|---|---|---|
| Score a job | 1 per new job (never re-scored) | ~$0.015 / ~$0.003 (half with batch) |
| Read an alert email | 1 per email (never re-read) | ~$0.03 / ~$0.006 |
| CV analysis | 1 per upload | ~$0.05 / ~$0.01 |
| Draft an application | 1 per click | ~$0.03 / ~$0.006 |
| Classify a possible reply | 1 per new email mentioning a company you applied to | ~$0.01 / ~$0.002 |

A typical month (a few alert emails a day, 10–30 new jobs scored a day in batch mode, some drafts) is roughly **$5–15 on Opus or $1–3 on Haiku**. Change the model in Preferences → *AI & automation*. The **AI spend** page (bottom-left) shows actual spend per feature, and `max jobs scored per run` caps what each run can spend.

## Why it stays cheap

- The free filter removes ~93% of jobs (590 fetched → 38 sent to Claude in testing). It filters on work type, your cities, pay (converting PHP/EUR/... into your currency), title, age and skill keywords. A posting that says "Onsite or Remote" counts as unknown and is left for Claude.
- Every job and every email is processed once. Cross-posted duplicates are detected.
- Alert emails are flattened to text, and every 300-character tracking link is swapped for a short `[L3]` reference.
- Your profile prompt is cached, and outputs are small JSON.
- Batch mode halves the scoring cost.

Alert emails only contain a snippet, so those jobs are scored on limited information. Claude caps their score at 80 and labels them "Limited info". Open the link for the full posting.

## Sources

| Source | How | Notes |
|---|---|---|
| JobStreet PH, OnlineJobs.ph, LinkedIn (Philippines) | Public search pages, one request per search term | Jobs open to people in the Philippines, from local and international companies. Snippets only, so scored as "Limited info" |
| LinkedIn, Indeed, JobStreet, OnlineJobs.ph | Your alert emails (IMAP, read-only) | Indeed blocks direct search, so use its alert emails. Senders are configurable in `profile.yaml → email_alerts.senders` |
| Remotive, RemoteOK, Jobicy, Himalayas, We Work Remotely | Public APIs/RSS | International remote jobs. Jobs limited to other countries ("Remote - US") are filtered out for free |
| Hacker News "Who is hiring?" | Algolia API | Monthly thread |
| Greenhouse / Lever / Ashby company boards | Public ATS APIs | Add your target companies in Preferences → Where to search |
| Arbeitnow | Public API | Mostly EU on-site (off by default) |

The feed terms ask for credit and a link back to the original posting. Every job links to its source. For personal use only.

## CLI

```
python run.py ui | run [--batch] | alerts | fetch | score | updates | collect | dry-run | report | stats
```

## Files

```
run.py                     CLI entry (python run.py ui = web app)
profile.yaml               your pay / work type / skills / filters (editable in the UI)
.env                       API key + mailbox credentials (never sent to Claude; gitignored)
jobs.db                    SQLite: jobs, scores, applications, timeline, CVs, token usage
data/cv/                   uploaded CVs
jobradar/sources.py        job feeds          jobradar/email_alerts.py  alert-email parsing
jobradar/prefilter.py      free filter        jobradar/scorer.py        Claude scoring (real-time / batch)
jobradar/cv.py             CV analysis        jobradar/applications.py  drafts, sending, update checks
jobradar/mailer.py         IMAP/SMTP          jobradar/web.py + templates/  the UI
```

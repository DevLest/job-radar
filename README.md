<div align="center">

# 📡 Job Radar

**Your personal job-hunting assistant. It finds jobs, picks the ones that fit you, and helps you apply.**

Runs on your own computer · Your data stays with you · Costs a few dollars a month

</div>

---

## 👋 What is Job Radar?

Job hunting means scrolling through hundreds of postings that don't fit: wrong pay, wrong city, wrong skills.
Job Radar does the scrolling for you.

| | What it does for you |
|---|---|
| 🔎 **Finds jobs** | Checks 10+ job sites and reads your LinkedIn, Indeed, JobStreet and OnlineJobs.ph alert emails. |
| 🧹 **Filters out the noise** | Drops jobs that pay too little, are in the wrong place, or don't match your skills. This step is free. |
| ⭐ **Rates what's left** | An AI (Claude) reads each remaining job and gives it a score out of 100, explained in plain words. |
| ✍️ **Helps you apply** | Writes a first draft of your application from your CV. You edit it, and **nothing is sent until you click Send**. |
| 📋 **Tracks everything** | A board shows every application. When a company replies, Job Radar spots the email and updates the status for you. |

```
  1. COLLECT              2. FILTER (free)           3. RATE (AI)            4. APPLY & TRACK
  Job sites + alerts ──►  pay, location, skills ──►  score out of 100 ──►   draft → you review → send
                          (~93% removed here)        with reasons           replies tracked automatically
```

---

## ✅ Before you start

You'll need these four things. Setting up takes about **15 minutes**.

| # | What | Why | Where to get it |
|---|---|---|---|
| 1 | **A Windows computer** | Job Radar runs on your PC. | You probably have this already. |
| 2 | **Python 3.12 or newer** | The program Job Radar is written in. | [python.org/downloads](https://www.python.org/downloads/) |
| 3 | **An Anthropic API key** | Lets Job Radar use the Claude AI to rate jobs. Pay-as-you-go, usually $1–15 a month. | [console.anthropic.com](https://console.anthropic.com/) |
| 4 | **A Gmail address** *(optional but recommended)* | So Job Radar can read job-alert emails, spot replies and send applications. | [gmail.com](https://mail.google.com/) |

---

## 🛠️ Installation (one time)

### Step 1: Install Python

1. Go to **[python.org/downloads](https://www.python.org/downloads/)** and click the big yellow **Download Python** button.
2. Open the file you downloaded.
3. ⚠️ **Important:** on the first screen, tick **"Add python.exe to PATH"** at the bottom. Then click **Install Now**.

   > If you forget to tick this box, Job Radar can't find Python. Run the installer again, choose **Modify**, and tick it.

### Step 2: Download Job Radar

**Easiest way (no tools needed):**

1. Open **[github.com/DevLest/job-radar](https://github.com/DevLest/job-radar)**.
2. Click the green **Code** button, then **Download ZIP**.
3. Right-click the downloaded ZIP and choose **Extract All...**. Put the folder somewhere easy to find, like `Documents\job-radar`.

**If you use Git:**

```powershell
git clone https://github.com/DevLest/job-radar.git
```

### Step 3: Start it

1. Open the `job-radar` folder.
2. Double-click **`start.bat`**.
3. A black window opens. **The first time takes 1–2 minutes** while it installs what it needs. Later starts take a few seconds.
4. Your browser opens **http://127.0.0.1:5000**. That's Job Radar. 🎉

> 💡 **Keep the black window open** while you use Job Radar. Closing it turns the app off.
> To start it again tomorrow, just double-click `start.bat` again.

---

## ⚙️ First-time setup (inside the app)

The **Home** page shows a checklist. Work through it from top to bottom:

### 1. Settings: connect the AI and your email

- **Anthropic API key:** in [console.anthropic.com](https://console.anthropic.com/), go to **API Keys → Create Key**, copy it, and paste it into Settings. Add some credit under **Billing** ($5 lasts most people a month or more).
- **Email (Gmail):** enter your Gmail address. For the password, **don't use your normal Gmail password.** Create an **App password** instead:
  1. Turn on 2-Step Verification for your Google account (required by Google).
  2. Go to **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**.
  3. Type "Job Radar" as the name and click **Create**.
  4. Copy the 16-letter password and paste it into Settings.

### 2. My CV: upload your CV

Drag your CV (PDF or Word) onto the page. The AI lists your skills, strengths, gaps and tips to improve your CV.
Click **Use it** to fill in your preferences automatically.

### 3. Preferences: tell it what you want

- **Pay:** "I want at least ___ per ___" (hour, day, month or year, in any currency).
- **Work setup:** pick the ones you accept: Remote, Hybrid or On-site.
- **Cities:** where hybrid or on-site work is OK for you.
- **Skills:** type a skill and press **Enter**.

### 4. Job sites: set up job alerts

On **LinkedIn, Indeed, JobStreet and OnlineJobs.ph**, create job alerts and have them sent to the Gmail address you entered in Settings.
Job Radar reads these emails for you.

### 5. Find jobs

Click **Find jobs** (top right). A progress card shows each step and tells you how many new matches it found.

---

## 📖 Everyday use

| Page | What you do there |
|---|---|
| 🏠 **Home** | See today's summary and the setup checklist. |
| 💼 **Jobs** | Browse jobs in tabs: *Top matches*, *Worth a look*, *Not rated yet*, *Filtered out* and *Hidden*. Each card shows the score, pay, work setup and your matching skills. |
| 📄 **A job's page** | Read why it got its score, then apply in 3 steps: **Write it for me** → edit the draft → **Send email** or **I've applied**. |
| 📋 **Applications** | A board: Drafts → Applied → Heard back → Interview → Offer → Closed. Drag a card to move it. |
| 💰 **AI spend** | See exactly how much the AI has cost you, per feature. |

**Handy tips**

- **Hide** a job you don't want. Changed your mind? Click **Undo**.
- Found a job somewhere else? Go to **More → Add a job I found** and paste it in.
- Job Radar warns you if you already applied **to the same role or company**.
- **Check application updates** looks for replies in your inbox, spots postings that were taken down, and reminds you to follow up after 14 days of silence.

> 🔒 **Job Radar never applies on your behalf.** On LinkedIn Easy Apply, JobStreet and company websites you apply yourself, then click **I've applied**. Automatic applying breaks those sites' rules and gets accounts banned.

---

## 💵 How much does it cost?

Job Radar itself is free. You only pay Anthropic for the AI, and only for jobs that pass the free filter.

| What | Cost each (best AI / budget AI) |
|---|---|
| Rate a job | ~$0.015 / ~$0.003 (half price in batch mode) |
| Read an alert email | ~$0.03 / ~$0.006 |
| Analyse your CV | ~$0.05 / ~$0.01 |
| Draft an application | ~$0.03 / ~$0.006 |
| Check whether an email is a reply | ~$0.01 / ~$0.002 |

**A typical month: about $5–15 with the best AI (Opus) or $1–3 with the budget AI (Haiku).**
Switch between them in **Preferences → AI & automation**. You can also set a limit on how many jobs are rated per run.

<details>
<summary><b>Why it stays cheap</b></summary>

- The free filter removes ~93% of jobs (in testing: 590 found → 38 sent to the AI).
- Every job and every email goes to the AI **at most once**. Duplicate postings are detected.
- Alert emails are shrunk to plain text before the AI reads them.
- Your profile is cached, and the AI's answers are kept short.
- Batch mode halves the rating cost.

Alert emails only contain a snippet of the job, so those jobs are capped at 80 and labelled **"Limited info"**. Open the link to read the full posting.

</details>

---

## 🔐 Your privacy

- Everything runs **on your computer**. The app can only be opened from your own PC, not from the internet.
- Your API key and email password are stored in a local `.env` file. They are **never sent to the AI** and never uploaded anywhere.
- Your CV, jobs and applications are stored in local files (`jobs.db`, `data/`, `profile.yaml`) and are never added to Git.
- Job Radar only **reads** your inbox. It sends an email only when you click **Send**.

---

## ❓ Troubleshooting

<details>
<summary><b>The black window opens and closes straight away, or says "python is not recognized"</b></summary>

Python isn't installed, or "Add python.exe to PATH" wasn't ticked. Run the Python installer again, choose **Modify**, tick that box, then double-click `start.bat` again.
</details>

<details>
<summary><b>The browser didn't open</b></summary>

Wait a few seconds, then open **http://127.0.0.1:5000** yourself.
</details>

<details>
<summary><b>"Anthropic API key missing/invalid"</b></summary>

Open **Settings** and paste your key again. Make sure your Anthropic account has credit under **Billing**.
</details>

<details>
<summary><b>"IMAP login failed" (email doesn't connect)</b></summary>

Use a Gmail **App password**, not your normal password, and check that 2-Step Verification is on. See [First-time setup](#1-settings-connect-the-ai-and-your-email).
</details>

<details>
<summary><b>No jobs show up</b></summary>

Check the **Filtered out** tab. Your filters may be too strict (pay too high, too few cities, or only one work setup selected). Loosen them in **Preferences** and click **Find jobs** again.
</details>

<details>
<summary><b>How do I update Job Radar?</b></summary>

Download the latest ZIP and replace the old files, **keeping** `.env`, `profile.yaml`, `jobs.db` and the `data` folder. If you used Git, run `git pull`. Then double-click `start.bat`. It installs anything new and closes the old version for you.
</details>

---

## 🤖 Run it automatically (optional)

**While the app is open:** in **Preferences → AI & automation**, pick tasks to run every few hours. Rating jobs is off by default, so it never spends money unless you turn that on.

**Even when the app is closed:** use Windows Task Scheduler. Open PowerShell and run the line below, replacing
`C:\job-radar` with the folder where you put Job Radar (a path without spaces is easiest):

```powershell
schtasks /create /tn JobRadar /sc daily /st 08:00 /tr "C:\job-radar\.venv\Scripts\python.exe C:\job-radar\run.py run --batch --wait 90"
```

This checks for new jobs and rates them every day at 8:00 AM. Run `schtasks /delete /tn JobRadar` to remove it.

---

## 🧑‍💻 For developers

<details>
<summary><b>Manual install (without start.bat)</b></summary>

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python run.py ui            # http://127.0.0.1:5000
```

`profile.yaml` is created from `profile.example.yaml` on first use. `.env` is written by the Settings page
(keys: `ANTHROPIC_API_KEY`, `IMAP_HOST/PORT/USER/PASSWORD/FOLDER`, `SMTP_HOST/PORT/USER/PASSWORD`, `FROM_NAME`).
</details>

<details>
<summary><b>CLI</b></summary>

```
python run.py ui | run [--batch] | alerts | fetch | score | updates | collect | dry-run | report | stats
```
</details>

<details>
<summary><b>Job sources</b></summary>

| Source | How | Notes |
|---|---|---|
| JobStreet PH, OnlineJobs.ph, LinkedIn (Philippines) | Public search pages, one request per search term | Jobs open to people in the Philippines. Snippets only, so scored as "Limited info" |
| LinkedIn, Indeed, JobStreet, OnlineJobs.ph | Your alert emails (IMAP, read-only) | Indeed blocks direct search, so use its alert emails. Senders are configurable in `profile.yaml → email_alerts.senders` |
| Remotive, RemoteOK, Jobicy, Himalayas, We Work Remotely | Public APIs/RSS | International remote jobs. Jobs limited to other countries ("Remote - US") are filtered out for free |
| Hacker News "Who is hiring?" | Algolia API | Monthly thread |
| Greenhouse / Lever / Ashby company boards | Public ATS APIs | Add your target companies in Preferences → Where to search |
| Arbeitnow | Public API | Mostly EU on-site (off by default) |

The feed terms ask for credit and a link back to the original posting. Every job links to its source. For personal use only.
</details>

<details>
<summary><b>Project layout</b></summary>

```
run.py                     CLI entry (python run.py ui = web app) -> jobradar/cli/
profile.yaml               your pay / work type / skills / filters (editable in the UI)
.env                       API key + mailbox credentials (never sent to Claude; gitignored)
jobs.db                    SQLite: jobs, scores, applications, timeline, CVs, token usage
data/cv/                   uploaded CVs
jobradar/app.py            Flask app factory          jobradar/container.py   wires every service
jobradar/domain/<feature>/ entity, repository, service, mapper, views and routes per feature
                           (jobs, applications, prefilter, scoring, alerts, cv, preferences, ...)
jobradar/sources/          one file per job feed      jobradar/pipeline/      task runner + scheduler
jobradar/lib/              SQLite, Claude, IMAP/SMTP, HTTP wrappers
jobradar/templates/        Atomic Design: components/{atoms,molecules,organisms}, layouts, pages
jobradar/static/           css/ + js/ (ES modules, no build step)
```

Architecture and coding rules for contributors (and AI assistants) are in `CLAUDE.md` and `.cursor/rules/`.
</details>

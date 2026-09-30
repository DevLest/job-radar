"""The Preferences page: tabs -> sections -> fields.

Field: (dotted profile path, label, kind, options, help). Kinds: text, textarea, int, float, select,
tags (list), lines, switch (bool), pills / cards (multi), pills1 / radiocards (single), fx (currency table)."""

CURRENCIES = ["USD", "PHP", "EUR", "GBP", "AUD", "SGD", "CAD", "JPY"]
WORK_CARDS = [("remote", "Remote", "Work from home, anywhere you're allowed", "globe"),
              ("hybrid", "Hybrid", "Some days in the office", "hybrid"),
              ("onsite", "On-site", "Full time at the office", "building")]
MODEL_CARDS = [("claude-opus-5-5", "Most accurate", "Opus 5.5 · ~$0.015 per job"),
               ("claude-sonnet-5-5", "Balanced", "Sonnet 5.5 · ~$0.008 per job"),
               ("claude-haiku-4-5", "Cheapest", "Haiku 4.5 · ~$0.003 per job")]
# Fields that only make sense when another field has one of the given values.
SHOW_IF = {"work_setup.onsite_locations": "work_setup.work_types:hybrid,onsite"}

PREFS = [
    ("work", "Pay & work style", "wallet", [
        {"title": "How much do you want to earn?", "layout": "pay",
         "desc": "Jobs that clearly pay less than your minimum are skipped automatically - no AI cost.",
         "fields": [("rate.minimum", "Minimum", "float", None, ""), ("rate.target", "Target", "float", None, ""),
                    ("rate.currency", "Currency", "select", CURRENCIES, ""),
                    ("rate.per", "Per", "select", ["hour", "day", "month", "year"], "")]},
        {"title": "How do you want to work?", "desc": "Pick everything you're open to.",
         "fields": [("work_setup.work_types", "", "cards", WORK_CARDS, ""),
                    ("work_setup.onsite_locations", "Cities where hybrid / on-site is OK", "tags", None,
                     "Hybrid and on-site jobs in other cities are skipped. Type a city and press Enter."),
                    ("work_setup.employment_types", "Contract type", "pills",
                     ["full-time", "part-time", "contract", "freelance"], "")]},
        {"title": "Currency conversion", "collapsed": True,
         "desc": "Lets a salary in another currency be compared with yours. Approximate rates are fine.",
         "fields": [("rate.fx_to_rate_currency", "", "fx", None, "One per line: CURRENCY = value of 1 unit in your currency")]},
    ]),
    ("me", "About me & skills", "user", [
        {"title": "About you", "desc": "Tip: upload your CV and this fills itself in.", "grid": True,
         "fields": [("candidate.name", "Name", "text", None, ""), ("candidate.title", "Headline", "text", None, ""),
                    ("candidate.years_experience", "Years of experience", "float", None, ""),
                    ("candidate.seniority", "Level", "pills1", ["junior", "mid", "senior", "lead"], ""),
                    ("candidate.based_in", "Based in", "text", None, ""), ("candidate.timezone", "Timezone", "text", None, ""),
                    ("candidate.languages_spoken", "Languages", "tags", None, ""),
                    ("candidate.summary", "Short summary", "textarea", None, "")]},
        {"title": "Your skills", "desc": "Type a skill and press Enter. Use the words job ads use (e.g. 'laravel', 'vue').",
         "fields": [("skills.primary", "Main skills", "tags", None, "Your core stack - these matter most"),
                    ("skills.secondary", "Other skills", "tags", None, ""),
                    ("skills.learning", "Currently learning", "tags", None, "")]},
    ]),
    ("search", "Where to search", "search", [
        {"title": "What to search for", "desc": "Every job site below is searched with these words.",
         "fields": [("sources.search_terms", "Search terms", "tags", None, "e.g. laravel, vue, full stack")]},
        {"title": "Job sites for the Philippines",
         "desc": "Jobs open to people in the Philippines, from local and international companies. "
                 "Searched directly - no account or login needed.",
         "grid": True,
         "fields": [("sources.jobstreet", "JobStreet", "switch", None, "ph.jobstreet.com"),
                    ("sources.onlinejobs", "OnlineJobs.ph", "switch", None, "Foreign employers hiring Filipinos remotely"),
                    ("sources.linkedin", "LinkedIn", "switch", None, "Remote jobs open to the Philippines")]},
        {"title": "International remote sites", "collapsed": True,
         "desc": "Global remote boards. Only jobs you can do from the Philippines are kept (worldwide, APAC or "
                 "Philippines) - jobs limited to other countries, like 'Remote - US', are skipped automatically.",
         "grid": True,
         "fields": [("sources.remotive", "Remotive", "switch", None, ""), ("sources.remoteok", "RemoteOK", "switch", None, ""),
                    ("sources.jobicy", "Jobicy", "switch", None, ""), ("sources.himalayas", "Himalayas", "switch", None, ""),
                    ("sources.weworkremotely", "We Work Remotely", "switch", None, ""),
                    ("sources.hackernews", "Hacker News", "switch", None, "Monthly 'Who is hiring?' thread"),
                    ("sources.arbeitnow", "Arbeitnow", "switch", None, "Mostly Europe")]},
        {"title": "Job-alert emails", "collapsed": True,
         "desc": "Also read the job alerts that LinkedIn, Indeed, JobStreet and OnlineJobs.ph email you. "
                 "This is the only way to get Indeed jobs - Indeed blocks direct searching.",
         "fields": [("email_alerts.enabled", "Read my job-alert emails", "switch", None, "Needs your mailbox connected in Settings"),
                    ("email_alerts.lookback_days", "Look back (days)", "int", None, "")]},
        {"title": "Companies you'd love to work for", "collapsed": True,
         "desc": "Watch their careers pages directly. Use the name from the careers link.",
         "fields": [("companies.greenhouse", "Greenhouse boards", "tags", None, "boards.greenhouse.io/<name>"),
                    ("companies.lever", "Lever boards", "tags", None, "jobs.lever.co/<name>"),
                    ("companies.ashby", "Ashby boards", "tags", None, "jobs.ashbyhq.com/<name>")]},
    ]),
    ("filters", "Filters", "filter", [
        {"title": "Job titles", "desc": "Quick, free filtering before the AI looks at anything.",
         "fields": [("filters.title_include", "Show titles containing any of", "tags", None, ""),
                    ("filters.title_exclude", "Never show titles containing", "tags", None, ""),
                    ("filters.max_age_days", "Ignore jobs older than (days)", "int", None, ""),
                    ("filters.min_keyword_score", "How many of your skills must appear", "int", None,
                     "Main skill = 3 points, other skill = 1 point")]},
        {"title": "Remote job locations", "desc": "Remote jobs often say where you must live.",
         "fields": [("work_setup.allowed_locations", "Locations that include you", "tags", None, "e.g. worldwide, apac, philippines"),
                    ("work_setup.reject_locations", "Always skip when it says", "tags", None, "e.g. us only"),
                    ("work_setup.strict_location", "Skip remote jobs whose location doesn't match", "switch", None,
                     "Saves AI cost. Turn off to see more borderline jobs."),
                    ("work_setup.max_timezone_overlap_hours_needed", "Hours of timezone overlap you can do", "int", None, "")]},
        {"title": "Deal breakers", "desc": "The AI marks these jobs as 'skip'.",
         "fields": [("deal_breakers", "", "lines", None, "One per line")]},
    ]),
    ("ai", "AI & automation", "sparkles", [
        {"title": "AI model", "desc": "Used to rate jobs, read alert emails, analyze your CV and write drafts.",
         "fields": [("claude.model", "", "radiocards", MODEL_CARDS, ""),
                    ("claude.effort", "Thinking effort", "pills1", ["low", "medium", "high"], "Higher is slower and costs more"),
                    ("claude.max_jobs_per_run", "Max jobs rated per run", "int", None, "A hard cap on spend per run"),
                    ("claude.max_description_chars", "Max job description length sent", "int", None, "")]},
        {"title": "Automatic checks", "desc": "While this app is open, it can check for jobs and replies on a timer.",
         "fields": [("automation.enabled", "Check automatically", "switch", None, ""),
                    ("automation.interval_hours", "Every (hours)", "float", None, ""),
                    ("automation.tasks", "What to do", "pills", ["alerts", "fetch", "score", "updates"],
                     "alerts = alert emails · fetch = job websites · score = AI rating (costs money) · updates = employer replies"),
                    ("automation.score_mode", "AI rating speed", "pills1", ["batch", "now"], "batch = half price, ready within ~1 hour")]},
    ]),
    ("apply", "Applications", "send", [
        {"title": "How your drafts sound", "desc": "",
         "fields": [("applications.tone", "Tone", "text", None, "e.g. professional, warm, concise"),
                    ("applications.sender_signature", "Email signature", "textarea", None, "Name, phone, LinkedIn - one per line")]},
    ]),
]


def all_fields():
    for _, _, _, sections in PREFS:
        for section in sections:
            yield from section["fields"]

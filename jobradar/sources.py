"""Job sources. No LLM calls - each fetcher returns a list of normalized Job objects.

International remote boards use their public JSON/RSS feeds. The Philippine sites
(JobStreet PH, OnlineJobs.ph, LinkedIn Philippines) are read from their public, logged-out
search pages: a few requests per search term, never your account."""

from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

UA = {"User-Agent": "job-radar/0.1 (personal job search tool)"}
# The Philippine sites serve their public search pages to browsers only.
BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/140.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
SNIPPET_NOTE = "\n\n(From {site} search results - only a snippet is available; open the link for the full posting.)"


@dataclass
class Job:
    source: str
    ext_id: str
    title: str
    company: str
    url: str
    description: str = ""
    location: str = ""
    tags: list[str] = field(default_factory=list)
    salary_text: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: str = "year"          # hour | month | year
    currency: str = ""
    employment_type: str = ""
    remote: bool | None = None
    work_type: str = ""                  # remote | hybrid | onsite | "" (unknown)
    posted_at: str | None = None         # ISO-8601 UTC

    @property
    def id(self) -> str:
        return f"{self.source}:{self.ext_id}"


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def _iso(value) -> str | None:
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)):
            ts = value / 1000 if value > 10**11 else value
            return datetime.fromtimestamp(ts, timezone.utc).isoformat()
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        try:  # RFC-822 (RSS)
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(str(value)).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            return None


def work_type_from(text: str | None) -> str:
    """Single clear work type, or "" when unknown or mixed (e.g. "Onsite or Remote") -
    mixed postings are left for Claude instead of being filtered out."""
    t = (text or "").lower()
    found = {name for name, pat in (("hybrid", r"hybrid"), ("onsite", r"on-?site|in[- ]office"), ("remote", r"remote"))
             if re.search(pat, t)}
    return found.pop() if len(found) == 1 else ""


def _num(v) -> float | None:
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def parse_salary(text: str, default_currency: str = "PHP") -> tuple[float | None, float | None, str, str]:
    """'₱40,000 – ₱60,000 per month', '$7 - $10 per hour', 'Up to Php112k' -> (min, max, period, currency).
    Returns (None, None, ...) when no amount is found."""
    t = (text or "").lower()
    amounts = [float(n.replace(",", "")) * (1000 if k else 1)
               for n, k in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(k\b)?", t) if n.replace(",", "")]
    amounts = [a for a in amounts if a > 0]
    if not amounts:
        return None, None, "month", ""
    currency = ("USD" if re.search(r"\$|usd", t) else "PHP" if re.search(r"₱|php|peso", t) else default_currency)
    period = next((p for p, pat in (("hour", r"hour|/hr|\bhr\b"), ("day", r"(?:per|a|/)\s*day\b|daily"), ("week", r"week"),
                                    ("year", r"year|annual|/yr")) if re.search(pat, t)), "month")
    lo, hi = min(amounts[:2]), max(amounts[:2])
    if re.search(r"up to|max", t):
        lo = None
    return lo, hi, period, currency


def _keep(jobs: dict, term: str, job: Job):
    """Adds a search result, remembering which search terms found it. The Philippine sites only
    show a snippet, so the site's own match on e.g. "laravel" (it searched the full posting) counts
    as that skill. "php" is not credited: on these sites it is also the peso currency code."""
    job = jobs.setdefault(job.ext_id, job)
    if term and term.lower() != "php" and term not in job.tags:
        job.tags.append(term)


class Fetcher:
    def __init__(self, timeout: float = 30, work_types: list[str] | None = None, max_age_days: int = 30):
        self.http = httpx.Client(headers=UA, timeout=timeout, follow_redirects=True)
        self.work_types = work_types or ["remote", "hybrid", "onsite"]
        self.max_age_days = max_age_days or 30

    def get_json(self, url: str, **params):
        r = self.http.get(url, params=params or None)
        r.raise_for_status()
        return r.json()

    def get_page(self, url: str, **params) -> str:
        r = self.http.get(url, params=params or None, headers=BROWSER)
        r.raise_for_status()
        return r.text

    # --- Philippine job sites ----------------------------------------------

    def jobstreet(self, terms: list[str]) -> list[Job]:
        # Only ask for the ways of working you accept. JobStreet leaves on-site jobs unlabeled.
        arrangements = ",".join(c for wt, c in (("onsite", "1"), ("hybrid", "2"), ("remote", "3"))
                                if wt in self.work_types)
        jobs = {}
        for term in terms or [""]:
            data = self.get_json("https://ph.jobstreet.com/api/jobsearch/v5/search", siteKey="PH-Main",
                                 keywords=term, page=1, pageSize=100, sortmode="ListedDate", locale="en-PH",
                                 workarrangement=arrangements)
            for j in data.get("data", []):
                lo, hi, period, cur = parse_salary(j.get("salaryLabel") or "")
                arrangement = (j.get("workArrangements") or {}).get("displayText") or ""
                locs = [l.get("label", "") for l in j.get("locations") or []]
                _keep(jobs, term, Job(
                    source="jobstreet", ext_id=str(j["id"]), title=j.get("title", ""),
                    company=j.get("companyName") or (j.get("advertiser") or {}).get("description", ""),
                    url=f"https://ph.jobstreet.com/job/{j['id']}",
                    description=(j.get("teaser") or "") + "\n" + "\n".join(j.get("bulletPoints") or [])
                                + SNIPPET_NOTE.format(site="JobStreet"),
                    location=", ".join(locs + ["Philippines"]),
                    tags=[c["subclassification"]["description"] for c in j.get("classifications") or []
                          if c.get("subclassification")],
                    salary_text=j.get("salaryLabel") or "", salary_min=lo, salary_max=hi,
                    salary_period=period, currency=cur, employment_type=", ".join(j.get("workTypes") or []),
                    work_type=work_type_from(arrangement) if arrangement else "onsite", posted_at=_iso(j.get("listingDate")),
                ))
        return list(jobs.values())

    def onlinejobs(self, terms: list[str]) -> list[Job]:
        # OnlineJobs.ph only lists remote jobs from employers hiring Filipinos.
        jobs = {}
        for term in terms or [""]:
            page = self.get_page("https://www.onlinejobs.ph/jobseekers/jobsearch", jobkeyword=term)
            for card in page.split("<!-- Start -->")[1:]:
                link = re.search(r'href="(/jobseekers/job/[^"]+?-(\d+))"', card)
                title = re.search(r"<h4[^>]*>(.*?)<span", card, re.S)
                if not (link and title):
                    continue
                kind = re.search(r'<span class="badge[^"]*">([^<]+)</span>', card)
                pay = re.search(r'icon-round-dollar.*?<dd class="col">(.*?)</dd>', card, re.S)
                desc = re.search(r'<div class="desc[^"]*">(.*?)<a href', card, re.S)
                posted = re.search(r'data-temp-2="([^"]+)"', card)
                pay_text = strip_html(pay.group(1)) if pay else ""
                lo, hi, period, cur = parse_salary(pay_text)
                _keep(jobs, term, Job(
                    source="onlinejobs", ext_id=link.group(2), title=strip_html(title.group(1)),
                    company="",  # employers are hidden until you open the posting
                    url="https://www.onlinejobs.ph" + link.group(1),
                    description=strip_html(desc.group(1) if desc else "") + SNIPPET_NOTE.format(site="OnlineJobs.ph"),
                    location="Philippines (remote)", tags=re.findall(r"class='badge'>([^<]+)<", card),
                    salary_text=pay_text if pay_text.upper() != "TBD" else "", salary_min=lo, salary_max=hi,
                    salary_period=period, currency=cur,
                    employment_type="" if not kind or kind.group(1).strip() == "Any" else kind.group(1).strip(),
                    remote=True, work_type="remote",
                    posted_at=_iso(posted.group(1).replace(" ", "T")) if posted else None,
                ))
        return list(jobs.values())

    def linkedin(self, terms: list[str]) -> list[Job]:
        # LinkedIn's logged-out job search for jobs open to candidates in the Philippines (remote ones
        # include foreign companies hiring there). One request per search term and work type,
        # with a pause between them to stay polite.
        codes = {"onsite": "1", "remote": "2", "hybrid": "3"}
        jobs = {}
        for term in terms or [""]:
            for wt in self.work_types:
                page = self.get_page("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                                     keywords=term, location="Philippines", f_WT=codes[wt],
                                     f_TPR=f"r{self.max_age_days * 86400}", start=0)
                time.sleep(1.5)
                for card in page.split("<li>")[1:]:
                    jid = re.search(r"urn:li:jobPosting:(\d+)", card)
                    title = re.search(r'base-search-card__title">(.*?)</h3>', card, re.S)
                    if not (jid and title):
                        continue
                    company = re.search(r'base-search-card__subtitle">(.*?)</h4>', card, re.S)
                    loc = re.search(r'job-search-card__location">(.*?)</span>', card, re.S)
                    pay = re.search(r'job-search-card__salary-info">(.*?)</span>', card, re.S)
                    date = re.search(r'<time[^>]*datetime="([^"]+)"', card)
                    pay_text = strip_html(pay.group(1)) if pay else ""
                    lo, hi, period, cur = parse_salary(pay_text)
                    location = strip_html(loc.group(1)) if loc else "Philippines"
                    _keep(jobs, term, Job(
                        source="linkedin", ext_id=jid.group(1), title=strip_html(title.group(1)),
                        company=strip_html(company.group(1)) if company else "",
                        url=f"https://www.linkedin.com/jobs/view/{jid.group(1)}",
                        description=SNIPPET_NOTE.format(site="LinkedIn").strip(),
                        location=location if "philippines" in location.lower() else location + ", Philippines",
                        salary_text=pay_text, salary_min=lo, salary_max=hi, salary_period=period, currency=cur,
                        remote=wt == "remote", work_type=wt, posted_at=_iso(date.group(1)) if date else None,
                    ))
        return list(jobs.values())

    # --- aggregators -------------------------------------------------------

    def remotive(self, terms: list[str]) -> list[Job]:
        # Remotive asks callers to keep volume low; one request per search term.
        jobs = {}
        for term in terms or [""]:
            data = self.get_json("https://remotive.com/api/remote-jobs", search=term, limit=100)
            for j in data.get("jobs", []):
                jobs[j["id"]] = Job(
                    source="remotive", ext_id=str(j["id"]), title=j["title"],
                    company=j["company_name"], url=j["url"],
                    description=strip_html(j.get("description")),
                    location=j.get("candidate_required_location") or "",
                    tags=j.get("tags") or [], salary_text=j.get("salary") or "",
                    employment_type=j.get("job_type") or "", remote=True,
                    posted_at=_iso(j.get("publication_date")),
                )
        return list(jobs.values())

    def remoteok(self, terms: list[str]) -> list[Job]:
        data = self.get_json("https://remoteok.com/api")
        out = []
        for j in data[1:]:  # element 0 is the legal notice
            out.append(Job(
                source="remoteok", ext_id=str(j["id"]), title=j.get("position", ""),
                company=(j.get("company") or "").strip(), url=j.get("url", ""),
                description=strip_html(j.get("description")), location=j.get("location") or "",
                tags=j.get("tags") or [], salary_min=_num(j.get("salary_min")),
                salary_max=_num(j.get("salary_max")), currency="USD" if _num(j.get("salary_min")) else "",
                remote=True, posted_at=_iso(j.get("date")),
            ))
        return out

    def jobicy(self, terms: list[str]) -> list[Job]:
        jobs = {}
        for term in terms or [""]:
            params = {"count": 50}
            if term:
                params["tag"] = term
            data = self.get_json("https://jobicy.com/api/v2/remote-jobs", **params)
            for j in data.get("jobs", []):
                jobs[j["id"]] = Job(
                    source="jobicy", ext_id=str(j["id"]), title=html.unescape(j["jobTitle"]),
                    company=j["companyName"], url=j["url"],
                    description=strip_html(j.get("jobDescription")), location=j.get("jobGeo") or "",
                    tags=(j.get("jobIndustry") or []) + [j.get("jobLevel") or ""],
                    salary_min=_num(j.get("annualSalaryMin")), salary_max=_num(j.get("annualSalaryMax")),
                    currency=j.get("salaryCurrency") or "",
                    employment_type=", ".join(j.get("jobType") or []), remote=True,
                    posted_at=_iso(j.get("pubDate")),
                )
        return list(jobs.values())

    def himalayas(self, terms: list[str]) -> list[Job]:
        jobs = {}
        for term in terms or [""]:
            data = self.get_json("https://himalayas.app/jobs/api/search", q=term)
            for j in data.get("jobs", []):
                locs = j.get("locationRestrictions") or []
                period = {"hourly": "hour", "monthly": "month"}.get(j.get("salaryPeriod"), "year")
                jobs[j["guid"]] = Job(
                    source="himalayas", ext_id=j["guid"].rstrip("/").rsplit("/", 1)[-1],
                    title=j["title"], company=j["companyName"], url=j.get("applicationLink") or j["guid"],
                    description=strip_html(j.get("description")),
                    # Long country lists are summarized so the location filter can still match them.
                    location="Worldwide" if not locs else ", ".join(locs),
                    tags=(j.get("categories") or []) + (j.get("seniority") or []),
                    salary_min=_num(j.get("minSalary")), salary_max=_num(j.get("maxSalary")),
                    salary_period=period, currency=j.get("currency") or "",
                    employment_type=j.get("employmentType") or "", remote=True,
                    posted_at=_iso(j.get("pubDate")),
                )
        return list(jobs.values())

    def weworkremotely(self, terms: list[str]) -> list[Job]:
        feeds = ["remote-programming-jobs", "remote-full-stack-programming-jobs",
                 "remote-back-end-programming-jobs", "remote-front-end-programming-jobs"]
        jobs = {}
        for feed in feeds:
            r = self.http.get(f"https://weworkremotely.com/categories/{feed}.rss")
            r.raise_for_status()
            for item in ET.fromstring(r.content).iter("item"):
                link = item.findtext("link") or ""
                raw_title = item.findtext("title") or ""
                company, _, title = raw_title.partition(": ")
                jobs[link] = Job(
                    source="weworkremotely", ext_id=link.rstrip("/").rsplit("/", 1)[-1],
                    title=title or raw_title, company=company if title else "", url=link,
                    description=strip_html(item.findtext("description")),
                    location=item.findtext("region") or "", employment_type=item.findtext("type") or "",
                    remote=True, posted_at=_iso(item.findtext("pubDate")),
                )
        return list(jobs.values())

    def hackernews(self, terms: list[str]) -> list[Job]:
        hits = self.get_json("https://hn.algolia.com/api/v1/search_by_date",
                             tags="story,author_whoishiring", hitsPerPage=10)["hits"]
        story = next((h for h in hits if h["title"].startswith("Ask HN: Who is hiring?")), None)
        if not story:
            return []
        thread = self.get_json(f"https://hn.algolia.com/api/v1/items/{story['objectID']}")
        out = []
        for c in thread.get("children", []):
            text = strip_html(c.get("text"))
            if not text:
                continue
            # Convention: first line is "Company | Role | Location | Remote | Salary"
            first = text.split("\n", 1)[0]
            parts = [p.strip() for p in first.split("|")]
            out.append(Job(
                source="hackernews", ext_id=str(c["id"]),
                title=(" | ".join(parts[1:3]) if len(parts) > 1 else first)[:120],
                company=parts[0][:80], url=f"https://news.ycombinator.com/item?id={c['id']}",
                description=text, location=" | ".join(parts[2:]) if len(parts) > 2 else "",
                remote=True if re.search(r"(?i)\bremote\b", first) else None,
                work_type=work_type_from(first), posted_at=_iso(c.get("created_at")),
            ))
        return out

    def arbeitnow(self, terms: list[str]) -> list[Job]:
        data = self.get_json("https://www.arbeitnow.com/api/job-board-api")
        return [Job(
            source="arbeitnow", ext_id=j["slug"], title=j["title"], company=j["company_name"],
            url=j["url"], description=strip_html(j.get("description")), location=j.get("location") or "",
            tags=j.get("tags") or [], employment_type=", ".join(j.get("job_types") or []),
            remote=bool(j.get("remote")), work_type="remote" if j.get("remote") else work_type_from(j.get("location")),
            posted_at=_iso(j.get("created_at")),
        ) for j in data.get("data", [])]

    # --- company boards (ATS APIs) ------------------------------------------

    def greenhouse(self, slug: str) -> list[Job]:
        data = self.get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", content="true")
        return [Job(
            source="greenhouse", ext_id=f"{slug}-{j['id']}", title=j["title"],
            company=j.get("company_name") or slug, url=j["absolute_url"],
            description=strip_html(html.unescape(j.get("content") or "")),
            location=(j.get("location") or {}).get("name", ""),
            work_type=work_type_from((j.get("location") or {}).get("name", "")),
            posted_at=_iso(j.get("first_published") or j.get("updated_at")),
        ) for j in data.get("jobs", [])]

    def lever(self, slug: str) -> list[Job]:
        data = self.get_json(f"https://api.lever.co/v0/postings/{slug}", mode="json")
        out = []
        for j in data:
            cats = j.get("categories") or {}
            sr = j.get("salaryRange") or {}
            out.append(Job(
                source="lever", ext_id=j["id"], title=j["text"], company=slug, url=j["hostedUrl"],
                description="\n".join(filter(None, [j.get("descriptionPlain"), j.get("additionalPlain")])),
                location=", ".join(cats.get("allLocations") or [cats.get("location") or ""]),
                employment_type=cats.get("commitment") or "",
                salary_min=_num(sr.get("min")), salary_max=_num(sr.get("max")), currency=sr.get("currency") or "",
                salary_period={"per-hour-wage": "hour", "per-month-salary": "month"}.get(sr.get("interval"), "year"),
                remote=(j.get("workplaceType") == "remote") if j.get("workplaceType") else None,
                work_type=work_type_from(j.get("workplaceType")),
                posted_at=_iso(j.get("createdAt")),
            ))
        return out

    def ashby(self, slug: str) -> list[Job]:
        data = self.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", includeCompensation="true")
        out = []
        for j in data.get("jobs", []):
            if not j.get("isListed", True):
                continue
            comp = (j.get("compensation") or {}).get("scrapeableCompensationSalarySummary") or ""
            out.append(Job(
                source="ashby", ext_id=j["id"], title=j["title"], company=slug, url=j["jobUrl"],
                description=j.get("descriptionPlain") or strip_html(j.get("descriptionHtml")),
                location=", ".join(filter(None, [j.get("location")] +
                                          [s.get("location") for s in j.get("secondaryLocations") or []])),
                salary_text=comp, employment_type=j.get("employmentType") or "",
                remote=j.get("isRemote"),
                work_type=work_type_from(j.get("workplaceType")) or ("remote" if j.get("isRemote") else ""),
                posted_at=_iso(j.get("publishedAt")),
            ))
        return out


PH_SITES = ["jobstreet", "onlinejobs", "linkedin"]
AGGREGATORS = PH_SITES + ["remotive", "remoteok", "jobicy", "himalayas", "weworkremotely", "hackernews", "arbeitnow"]
BOARDS = ["greenhouse", "lever", "ashby"]


def fetch_all(profile: dict, log=print) -> list[Job]:
    f = Fetcher(work_types=(profile.get("work_setup") or {}).get("work_types"),
                max_age_days=(profile.get("filters") or {}).get("max_age_days") or 30)
    src_cfg = profile.get("sources") or {}
    terms = src_cfg.get("search_terms") or []
    jobs: list[Job] = []
    for name in AGGREGATORS:
        if not src_cfg.get(name, False):
            continue
        try:
            got = getattr(f, name)(terms)
            log(f"  {name:<15} {len(got):>5} jobs")
            jobs += got
        except Exception as e:  # one broken source must not stop the run
            log(f"  {name:<15} FAILED: {e}")
    for board in BOARDS:
        for slug in (profile.get("companies") or {}).get(board) or []:
            try:
                got = getattr(f, board)(slug)
                log(f"  {board}:{slug:<10} {len(got):>5} jobs")
                jobs += got
            except Exception as e:
                log(f"  {board}:{slug:<10} FAILED: {e}")
    return jobs

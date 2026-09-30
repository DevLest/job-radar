"""Fill the profile from a CV analysis. Skills are added to (or replace) what you have."""

from __future__ import annotations

from ...shared.utils.text_utils import unique

SKILL_KEYS = (("primary", "primary_skills"), ("secondary", "secondary_skills"), ("learning", "learning_skills"))


def apply_to_profile(profile: dict, analysis: dict, replace_skills: bool = False) -> dict:
    candidate = profile.setdefault("candidate", {})
    candidate.update(title=analysis["headline"], years_experience=analysis["years_experience"],
                     seniority=analysis["seniority"], summary=analysis["summary"])
    if analysis["full_name"]:
        candidate["name"] = analysis["full_name"]
    if analysis["based_in"]:
        candidate["based_in"] = analysis["based_in"]
    if analysis["languages_spoken"]:
        candidate["languages_spoken"] = analysis["languages_spoken"]
    skills = profile.setdefault("skills", {})
    for key, source in SKILL_KEYS:
        found = [skill.lower() for skill in analysis[source]]
        skills[key] = found if replace_skills else unique((skills.get(key) or []) + found)
    filters = profile.setdefault("filters", {})
    filters["title_include"] = unique((filters.get("title_include") or []) + analysis["title_keywords"])
    return profile

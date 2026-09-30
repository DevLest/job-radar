SCHEMA = {
    "type": "object",
    "properties": {
        "full_name": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "headline": {"type": "string", "description": "Best-fit job title, e.g. 'Full-stack Laravel Developer'"},
        "years_experience": {"type": "number"},
        "seniority": {"type": "string", "enum": ["junior", "mid", "senior", "lead"]},
        "summary": {"type": "string", "description": "2-3 sentence professional summary in third person"},
        "based_in": {"type": "string"},
        "languages_spoken": {"type": "array", "items": {"type": "string"}},
        "primary_skills": {"type": "array", "items": {"type": "string"},
                           "description": "Core skills with real work evidence, lowercase, as job ads spell them (max 10)"},
        "secondary_skills": {"type": "array", "items": {"type": "string"}, "description": "Supporting skills (max 15)"},
        "learning_skills": {"type": "array", "items": {"type": "string"}, "description": "Mentioned but little evidence"},
        "title_keywords": {"type": "array", "items": {"type": "string"},
                           "description": "Lowercase words that appear in titles of jobs this person should see"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}, "description": "What employers will see as missing"},
        "cv_tips": {"type": "array", "items": {"type": "string"}, "description": "Concrete CV improvements (max 6)"},
    },
    "required": ["full_name", "email", "phone", "headline", "years_experience", "seniority", "summary", "based_in",
                 "languages_spoken", "primary_skills", "secondary_skills", "learning_skills", "title_keywords",
                 "strengths", "gaps", "cv_tips"],
    "additionalProperties": False,
}

SYSTEM = """You are an experienced tech recruiter. Analyze the candidate's CV and return a strict JSON profile.
Only claim skills the CV supports; put weakly-evidenced skills under learning_skills. Estimate years of
professional experience from dates. Be direct and specific in gaps and cv_tips."""

MAX_CV_CHARS = 40000
MIN_TEXT_CHARS = 200  # less than this from a PDF means it's scanned: Claude reads the pages instead

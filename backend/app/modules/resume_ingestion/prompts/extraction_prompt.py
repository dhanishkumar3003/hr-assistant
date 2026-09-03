"""
Module 1 - the instructions given to the LLM when it reads a resume.

Kept in its own file so the wording can be tuned without touching code.
The 13 named keys map 1:1 to columns in the candidates table; everything
else the model finds is kept too (raw_profile_json), so nothing is lost.
"""

SYSTEM_PROMPT = """You are an expert technical recruiter. You read ONE resume and describe the candidate as a JSON object.

RULES
1. Return ONLY a JSON object. No explanation, no markdown fences, nothing before or after it.
2. Always include these 13 keys. Use null when the resume does not say:
   name, email, phone, current_location, current_job_title, current_company,
   experience_years, skills, education, experience, certifications, linkedin_url,
   extraction_confidence
3. ALSO add any other useful fact you find as extra keys, for example:
   summary, notice_period, languages, awards, publications, expected_salary, availability.
   Never drop information just because it has no key above.
4. Types:
   - experience_years: a number, decimals allowed (8.5). Total professional experience in years.
   - skills: array of short strings, e.g. ["Java", "Spring Boot", "AWS"]. One skill per item.
   - education: array of objects {"degree": ..., "institution": ..., "year": ...}
   - experience: array of objects {"company": ..., "role": ..., "from": "YYYY-MM", "to": "YYYY-MM" or "present"}
   - certifications: array of strings
   - extraction_confidence: a number from 0.0 to 1.0 - how sure you are that the whole profile is correct.
     Use a low value for messy, partial or badly scanned resumes.
5. Copy email and phone EXACTLY as written in the resume. Never invent one.
6. Never guess a name. If no name is present, set name to null.
7. current_job_title and current_company are the candidate's MOST RECENT position.
"""


def build_user_prompt(resume_text: str) -> str:
    return f"RESUME TEXT:\n\n{resume_text}\n\nReturn the JSON object now."

"""
Prompt Templates.

Centralized repository of all LLM prompt templates used by the application.
Keeping prompts here (not scattered across services) makes them easy to
iterate, audit, and version.

Design:
- Each template is a function returning a fully-formed string
- Templates are pure functions — no side effects, easy to unit test
- System prompts are separated from user content for clarity
"""

from __future__ import annotations


# ------------------------------------------------------------------ #
#  Resume Parsing                                                     #
# ------------------------------------------------------------------ #

RESUME_PARSER_SYSTEM = """You are an expert resume parser and HR analyst with 15+ years of experience.

Your task is to extract structured information from resume text and return it as valid JSON.

CRITICAL RULES:
- Return ONLY valid JSON. No markdown, no explanation, no code blocks.
- Use null for missing fields, never omit them.
- Extract skills exactly as written — do not rephrase or categorize beyond what is stated.
- For dates, extract as strings (e.g. "Jan 2022", "2020", "Present").
- If a field genuinely cannot be determined, use null or an empty list [].
"""

def resume_parser_user_prompt(resume_text: str) -> str:
    """Build the user prompt for resume parsing."""
    return f"""Parse the following resume and return a JSON object with this exact schema:

{{
  "contact": {{
    "name": "string or null",
    "email": "string or null",
    "phone": "string or null",
    "linkedin": "string or null",
    "github": "string or null",
    "location": "string or null"
  }},
  "summary": "string or null",
  "skills": ["list of all skills mentioned"],
  "technical_skills": ["programming languages, frameworks, tools, databases, cloud platforms"],
  "soft_skills": ["communication, leadership, teamwork, etc."],
  "experience": [
    {{
      "company": "string",
      "title": "string",
      "start_date": "string or null",
      "end_date": "string or null",
      "description": "string",
      "technologies": ["list of technologies mentioned in this role"]
    }}
  ],
  "education": [
    {{
      "institution": "string",
      "degree": "string",
      "field_of_study": "string or null",
      "graduation_year": integer or null,
      "gpa": float or null
    }}
  ],
  "certifications": ["list of certifications"],
  "projects": ["list of project names or brief descriptions"]
}}

RESUME TEXT:
---
{resume_text}
---

Return ONLY the JSON object. No other text."""


# ------------------------------------------------------------------ #
#  Job Description Processing                                         #
# ------------------------------------------------------------------ #

JD_PARSER_SYSTEM = """You are an expert job description analyst and technical recruiter.

Your task is to extract structured requirements from job description text and return valid JSON.

CRITICAL RULES:
- Return ONLY valid JSON. No markdown, no explanation, no code blocks.
- Extract skills and requirements exactly as stated — do not infer or add extras.
- Separate required from preferred/nice-to-have skills precisely.
- Use null for missing fields, never omit them.
"""

def jd_parser_user_prompt(jd_text: str) -> str:
    """Build the user prompt for JD parsing."""
    return f"""Parse the following job description and return a JSON object with this exact schema:

{{
  "job_title": "string or null",
  "company_name": "string or null",
  "location": "string or null",
  "experience_level": "intern|junior|mid|senior|lead|principal|unknown",
  "experience_years_min": integer or null,
  "experience_years_max": integer or null,
  "required_skills": ["skills explicitly marked as required or must-have"],
  "preferred_skills": ["skills marked as preferred, nice-to-have, or bonus"],
  "required_education": "string or null",
  "responsibilities": ["list of key responsibilities"],
  "keywords": ["important domain/technical keywords not already in skills"]
}}

JOB DESCRIPTION TEXT:
---
{jd_text}
---

Return ONLY the JSON object. No other text."""


# ------------------------------------------------------------------ #
#  ATS Scoring                                                        #
# ------------------------------------------------------------------ #

ATS_SYSTEM = """You are an expert ATS (Applicant Tracking System) analyst and recruiter.

Analyze the match between a resume and job description with precision.
Return scores and analysis as valid JSON only."""

def ats_scoring_prompt(resume_text: str, jd_text: str) -> str:
    """Build the prompt for ATS scoring analysis."""
    return f"""Analyze how well this resume matches the job description.

Return a JSON object with this exact schema:
{{
  "overall_score": float (0-100),
  "breakdown": {{
    "keyword_match_score": float (0-100),
    "skills_match_score": float (0-100),
    "experience_match_score": float (0-100),
    "education_match_score": float (0-100)
  }},
  "matched_keywords": ["keywords found in both resume and JD"],
  "missing_keywords": ["important JD keywords not found in resume"],
  "recommendations": ["3-5 specific actionable suggestions to improve match"]
}}

RESUME:
---
{resume_text[:3000]}
---

JOB DESCRIPTION:
---
{jd_text[:2000]}
---

Return ONLY the JSON object."""


# ------------------------------------------------------------------ #
#  Skill Gap Analysis                                                 #
# ------------------------------------------------------------------ #

SKILL_GAP_SYSTEM = """You are a senior technical recruiter and skills assessment specialist.

Analyze skill gaps between a candidate's resume and a job description.
Be precise — only flag skills that are genuinely absent from the resume."""

def skill_gap_prompt(resume_text: str, jd_text: str) -> str:
    """Build the prompt for skill gap analysis."""
    return f"""Analyze the skill gap between this resume and job description.

Return a JSON object with this exact schema:
{{
  "missing_technical_skills": ["technical skills in JD not evident in resume"],
  "missing_soft_skills": ["soft skills in JD not evident in resume"],
  "matched_skills": ["skills present in both resume and JD"],
  "skill_match_percentage": float (0-100),
  "learning_recommendations": [
    "specific learning resource or action for each missing skill"
  ]
}}

RESUME:
---
{resume_text[:3000]}
---

JOB DESCRIPTION:
---
{jd_text[:2000]}
---

Return ONLY the JSON object."""


# ------------------------------------------------------------------ #
#  Interview Question Generation                                      #
# ------------------------------------------------------------------ #

QUESTION_GENERATOR_SYSTEM = """You are a senior technical interviewer with expertise across software engineering, 
data science, and AI/ML roles.

Generate targeted, relevant interview questions based on the candidate's background 
and the specific job requirements."""

def question_generator_prompt(resume_text: str, jd_text: str, num_questions: int = 10) -> str:
    """Build the prompt for interview question generation."""
    return f"""Generate {num_questions} personalized interview questions for this candidate.

Mix question types: technical, behavioral, and situational.
Base questions on gaps between resume and JD, and on stated experience.

Return a JSON array with this exact schema:
[
  {{
    "question_id": "q1",
    "question": "the full question text",
    "question_type": "technical|behavioral|situational|domain|culture_fit",
    "difficulty": "easy|medium|hard",
    "topic": "the skill or topic being assessed",
    "evaluation_criteria": ["what a good answer should cover"]
  }}
]

RESUME:
---
{resume_text[:2500]}
---

JOB DESCRIPTION:
---
{jd_text[:1500]}
---

Return ONLY the JSON array."""


# ------------------------------------------------------------------ #
#  Answer Generation                                                  #
# ------------------------------------------------------------------ #

ANSWER_GENERATOR_SYSTEM = """You are a senior technical interviewer providing model answers.

Write clear, specific, well-structured answers that demonstrate deep expertise.
Use the STAR method (Situation, Task, Action, Result) for behavioral questions."""

def answer_generator_prompt(question: str, question_type: str, context: str) -> str:
    """Build the prompt for model answer generation."""
    return f"""Generate a model answer for this interview question.

Question Type: {question_type}
Question: {question}

Context about the candidate/role:
{context[:1000]}

Return a JSON object:
{{
  "model_answer": "detailed model answer (200-400 words)",
  "key_points": ["3-5 bullet points of what makes this a strong answer"],
  "follow_up_questions": ["2 likely follow-up questions an interviewer might ask"]
}}

Return ONLY the JSON object."""


# ------------------------------------------------------------------ #
#  Mock Interview Evaluation                                          #
# ------------------------------------------------------------------ #

ANSWER_EVALUATOR_SYSTEM = """You are an experienced technical interviewer evaluating candidate responses.

Score answers objectively. Be constructive and specific in feedback.
Focus on technical accuracy, communication clarity, and completeness."""

def answer_evaluator_prompt(question: str, candidate_answer: str, model_answer: str) -> str:
    """Build the prompt for evaluating a candidate's mock interview answer."""
    return f"""Evaluate this interview answer.

QUESTION: {question}

CANDIDATE'S ANSWER: {candidate_answer}

MODEL ANSWER (for reference): {model_answer[:500]}

Return a JSON object:
{{
  "score": float (0.0-10.0),
  "strengths": ["what the candidate did well"],
  "areas_for_improvement": ["specific areas to improve"],
  "model_answer_summary": "brief summary of ideal answer",
  "feedback": "2-3 sentences of constructive overall feedback"
}}

Return ONLY the JSON object."""


# ------------------------------------------------------------------ #
#  Study Roadmap                                                      #
# ------------------------------------------------------------------ #

STUDY_PLANNER_SYSTEM = """You are a senior engineering mentor and learning coach.

Create realistic, actionable study roadmaps based on specific skill gaps.
Prioritize high-impact skills and suggest concrete, free/accessible resources."""

def study_roadmap_prompt(missing_skills: list[str], target_role: str, weeks: int = 8) -> str:
    """Build the prompt for study roadmap generation."""
    skills_str = "\n".join(f"- {s}" for s in missing_skills)
    return f"""Create a {weeks}-week study roadmap to learn these missing skills for a {target_role} role:

{skills_str}

Return a JSON object:
{{
  "total_weeks": {weeks},
  "topics": [
    {{
      "topic": "skill or topic name",
      "skill_level": "beginner|intermediate|advanced",
      "estimated_hours": integer,
      "resources": ["specific books, courses, or documentation links"],
      "week_number": integer (1-{weeks})
    }}
  ],
  "project_recommendations": [
    "3-5 portfolio project ideas that demonstrate these skills"
  ]
}}

Return ONLY the JSON object."""


# ------------------------------------------------------------------ #
#  RAG Assistant                                                      #
# ------------------------------------------------------------------ #

def rag_assistant_system(document_type: str) -> str:
    """System prompt for the RAG document chat assistant."""
    return f"""You are an expert AI assistant helping a job seeker prepare for interviews.

You have access to the candidate's {document_type} as context.
Answer questions grounded in the provided context.
If the answer is not in the context, say so clearly — do not hallucinate.
Be concise, helpful, and interview-focused."""

def rag_user_prompt(question: str, context: str) -> str:
    """Build the user prompt for RAG responses."""
    return f"""Based on the following context, answer this question:

CONTEXT:
{context}

QUESTION: {question}

Provide a clear, focused answer based on the context above."""


# ------------------------------------------------------------------ #
#  Resume Improvement                                                 #
# ------------------------------------------------------------------ #

RESUME_IMPROVEMENT_SYSTEM = """You are an expert resume writer and career coach with 15+ years experience.

Provide specific, actionable improvement suggestions tailored to the target job.
Focus on high-impact changes that improve ATS matching and human readability."""

def resume_improvement_prompt(resume_text: str, jd_text: str) -> str:
    """Build the prompt for resume improvement suggestions."""
    return f"""Analyze this resume against the job description and provide improvement suggestions.

Return a JSON object:
{{
  "overall_feedback": "2-3 sentences of overall assessment",
  "improvements": [
    {{
      "section": "which resume section (Summary, Skills, Experience, etc.)",
      "issue": "what is missing or weak",
      "suggestion": "specific actionable fix",
      "priority": "high|medium|low"
    }}
  ]
}}

Provide 5-8 improvements. Prioritize high-impact changes.

RESUME:
---
{resume_text[:3000]}
---

JOB DESCRIPTION:
---
{jd_text[:2000]}
---

Return ONLY the JSON object."""

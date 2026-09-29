# AI Interview Preparation Assistant
 
An AI-powered application that helps job seekers prepare for interviews by analysing their resume against a specific job description. Rather than giving generic advice, it grounds every response in the candidate's actual resume and the actual job posting, using a Retrieval-Augmented Generation (RAG) pipeline. The goal is to give candidates a concrete, personalised sense of how well they match a role, what is missing from their resume, and how they would likely perform in a real interview for that position.
 
**Live Demo**: [ai-interview-assistant-c6bsnzql38aama7whyddos.streamlit.app](https://ai-interview-assistant-c6bsnzql38aama7whyddos.streamlit.app/)
 
---
 
## What It Does
 
Upload your resume and a job description, and the app gives you:
 
- **ATS Score** — how well your resume matches the job description
- **Skill Gap Analysis** — missing skills with learning recommendations
- **Resume Improvement Tips** — section-by-section suggestions
- **AI Chat Assistant** — ask questions about your resume or the job, grounded in your actual documents
- **Mock Interview** — practice with AI-generated questions and get scored on your answers
- **Analytics Dashboard** — an overall readiness score across everything above
---
 
## How It Works
 
1. Upload your resume (PDF/DOCX) and paste or upload a job description
2. The app extracts text and splits it into chunks, then converts those chunks into embeddings using a local Sentence Transformer model
3. Embeddings are stored in ChromaDB, a vector database, so relevant content can be retrieved later
4. When you ask a question or run an analysis, the app retrieves the most relevant chunks from your documents and sends them to Groq's GPT-OSS 120B along with your question — this is called RAG (Retrieval-Augmented Generation), and it's what keeps answers grounded in your actual resume and job description instead of generic responses
5. For scoring features (ATS, Skill Gap), the app combines exact keyword matching with the LLM's contextual understanding to produce a more accurate result than either approach alone
6. For Mock Interview, the LLM generates personalised questions based on your resume and the job, then evaluates your typed answers against a scoring rubric
---
 
## Tech Stack
 
| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| LLM | Groq API (GPT-OSS 120B, free tier) |
| RAG Framework | LangChain |
| Vector Database | ChromaDB |
| Embeddings | Sentence Transformers (all-MiniLM-L6-v2) |
| Document Processing | PyPDF, python-docx |
| Language | Python |
| Deployment | Docker, HuggingFace Spaces |
 

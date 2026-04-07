import os
import re
import urllib3
import asyncio
import time
from functools import lru_cache
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json

# --- LangChain Imports ---
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS  
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. SETUP MODEL & DB
print("... Loading Database ...")

# Using OpenAI's most cost-effective embedding model
embedding_model_name = "text-embedding-3-small"
embeddings = OpenAIEmbeddings(model=embedding_model_name)

# Load FAISS Database
vectorstore = FAISS.load_local("./faiss_db", embeddings, allow_dangerous_deserialization=True)

# Setting up the OpenAI LLM (gpt-4o-mini)
llm = ChatOpenAI(model="gpt-5-nano", temperature=0.3)

# --- COMPREHENSIVE INSTRUCTION PROMPT ---
template = """You are the LILIT LMS Expert Assistant. 
You have access to official documents (About, Courses, Contact, etc.) and website content.

CONTEXT:
{context}

QUESTION:
{question}

INSTRUCTIONS:
1. **CONTACT DETAILS:** If the user asks for "phone", "mobile", "hotline", "call", "mail", "email", or "address", ALWAYS check the context for:
   - Hotline: +94 70 438 8464
   - Help Line: +94 71 661 6699
   - Email: info@lilit.lk
   - Address: D/263/2, Magammana, Dehiowita.
   (List ALL of these if the user asks for general contact info). 

2. **LANGUAGE TRANSLATION:** If the context info is in Sinhala (e.g., course fees, duration) but the question is in English, TRANSLATE the details completely into English.

3. **COURSE DETAILS (CRITICAL FORMATTING):** If asked about courses, list EACH course in a separate paragraph. Do NOT combine them into one block of text. For each course, clearly list its Name, Duration, Course Fee, and a brief Explanation/Overview on separate lines using bullet points. Ensure there is a blank line between different courses. IMPORTANT: Always search the context carefully for course fee information - NEVER say "Not specified" if a fee amount is mentioned anywhere in the context. If a fee is truly not mentioned, you may say it then.

4. **Completeness:** Do not give short answers. If you find the info, give the full details found in the text files.

5. **CONCISENESS FOR MISSION & VISION:** If the user asks for the "Vision" or "Mission", provide ONLY the exact short statement. Do NOT add extra paragraphs, history, or educational philosophy from other texts.

HELPFUL ANSWER:"""

QA_CHAIN_PROMPT = PromptTemplate(input_variables=["context", "question"], template=template)

# 2. SETUP CHAIN
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})  # Reduced from 10 to 5 for faster retrieval

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

qa_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | QA_CHAIN_PROMPT
    | llm
    | StrOutputParser()
)

class ChatRequest(BaseModel):
    question: str

# --- Cache Layer for Live Data ---
class CachedData:
    def __init__(self, ttl_seconds=300):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            del self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, time.time())

cache = CachedData(ttl_seconds=7200)  # 2 hours cache

# --- Async Web Scraping Functions with Caching ---
async def get_live_course_count():
    cached = cache.get("course_count")
    if cached is not None:
        return cached
    
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get("https://lms.lilit.lk/all-courses", timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            course_links = set()
            for a in soup.find_all('a', href=True):
                if '/course-details/' in a['href']:
                    course_links.add(a['href'])
            count = len(course_links) if course_links else 5
            cache.set("course_count", count)
            return count
    except Exception as e:
        print(f"Error fetching course count: {e}")
        return 5

async def get_live_news_context():
    cached = cache.get("news_context")
    if cached is not None:
        return cached
    
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get("https://lms.lilit.lk/news", timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            for tag in soup(['nav', 'header', 'footer', 'aside', 'script', 'style']):
                tag.decompose()
            content = soup.get_text(separator='\n', strip=True)
            cache.set("news_context", content)
            return content
    except Exception as e:
        print(f"Error fetching news context: {e}")
        return ""

async def get_course_details_by_id(course_id):
    """Fetch course details from a specific course page with caching"""
    cache_key = f"course_{course_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        url = f"https://lms.lilit.lk/course-details/{course_id}"
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style tags
            for tag in soup(['nav', 'header', 'footer', 'aside', 'script', 'style']):
                tag.decompose()

            # Extract text content
            content = soup.get_text(separator='\n', strip=True)

            # Try to intelligently parse and structure the content
            # Look for common patterns in course pages
            structured = f"COURSE DATA FROM {url}\n\n{content}"

            cache.set(cache_key, structured)
            return structured
    except Exception as e:
        print(f"Error fetching course {course_id}: {e}")
        return ""

async def get_all_course_details():
    """Return cached course data for all courses (instant response)"""
    cache_key = "all_courses_data"
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    # Hardcoded fallback data (always available)
    hardcoded_data = """
=== COURSE ID: 2 ===
e-Certificate AI for All
DURATION: 4 Days
COURSE FEE: LKR 1,000
This course provides a foundational introduction to AI technology suitable for all learners.

=== COURSE ID: 3 ===
Web Design WordPress with AI
DURATION: 2 months
COURSE FEE: LKR 4,500
Learn professional web design using WordPress and AI tools. No coding required.

=== COURSE ID: 4 ===
Arduino With Future Robotics
DURATION: 3 months
COURSE FEE: LKR 5,000
Learn robotics, electronics, and programming with Arduino for hands-on projects.

=== COURSE ID: 5 ===
National Certificate in Web Development
DURATION: 6 months
COURSE FEE: LKR 30,000
Comprehensive web development program covering HTML, CSS, JavaScript, and modern frameworks.

=== COURSE ID: 6 ===
AI Study
DURATION: 4 days
COURSE FEE: LKR 100
Short intensive course to learn fundamental AI concepts and applications.

=== COURSE ID: 7 ===
AI Content Creation
DURATION: Flexible
COURSE FEE: LKR 1,000
Learn to create videos, graphics, and content using the latest AI technology.
"""

    cache.set(cache_key, hardcoded_data)
    return hardcoded_data

async def get_objectives_context():
    """Fetch objectives from About page with caching"""
    cached = cache.get("objectives")
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get("https://lms.lilit.lk/about", timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            for tag in soup(['nav', 'header', 'footer', 'aside', 'script', 'style']):
                tag.decompose()
            content = soup.get_text(separator='\n', strip=True)
            cache.set("objectives", content)
            return content
    except Exception as e:
        print(f"Error fetching objectives: {e}")
        return ""

# --- API Routes ---
@app.get("/")
def read_root():
    return FileResponse("index.html")

@app.post("/chat")
async def chat(payload: ChatRequest):
    print(f"Received Question: {payload.question}")
    
    async def generate_stream():
        try:
            q_lower = payload.question.lower()
            
            # 1. Intercept Course Count query
            if re.search(r'(how many|number of|count of|total).*courses', q_lower):
                count = await get_live_course_count()
                answer = f"LILIT currently offers {count} courses. You can view them all at https://lms.lilit.lk/all-courses."
                yield f"data: {json.dumps({'token': answer})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 2. Intercept Objectives query
            if re.search(r'\b(objective|objectives|aim|aims|goal|goals)\b', q_lower):
                objectives_text = await get_objectives_context()
                if objectives_text:
                    prompt = (
                        "You are a helpful assistant for LILIT LMS. Extract ALL objectives from the following text and present them clearly.\n"
                        "For each objective: **Title** + brief description. Separate each with a blank line.\n\n"
                        f"RAW CONTENT:\n{objectives_text[:3000]}"  # Limit context size
                    )
                    async for chunk in llm.astream(prompt):
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

            # 3. Intercept News query
            if re.search(r'\b(news|events|latest updates|happening)\b', q_lower):
                news_text = await get_live_news_context()
                if news_text:
                    prompt = (
                        "You are a helpful assistant for LILIT LMS. Extract ALL news items as a bulleted list.\n"
                        "For each: **Title** (bold), Date, Time, Author. Separate each with a blank line.\n\n"
                        f"RAW CONTENT:\n{news_text[:3000]}"  # Limit context size
                    )
                    async for chunk in llm.astream(prompt):
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

            # 4. Intercept SPECIFIC Course Queries - Use hardcoded data instead of live scraping
            if re.search(r'\b(ai for all|ai.for.all|certificate.ai.for.all|e-certificate ai)\b', q_lower):
                answer = "**e-Certificate AI for All**\n- Duration: 4 Days\n- Course Fee: LKR 1,000\n- Overview: This course provides a foundational introduction to AI technology suitable for all learners."
                yield f"data: {json.dumps({'token': answer})}\n\n"
                yield "data: [DONE]\n\n"
                return

            if re.search(r'\b(content creation|ai content|e-certificate ai content)\b', q_lower):
                answer = "**AI Content Creation**\n- Duration: Flexible\n- Course Fee: LKR 1,000\n- Overview: Learn to create videos, graphics, and content using the latest AI technology."
                yield f"data: {json.dumps({'token': answer})}\n\n"
                yield "data: [DONE]\n\n"
                return

            if re.search(r'\b(web design|wordpress|web design wordpress)\b', q_lower):
                answer = "**Web Design WordPress with AI**\n- Duration: 2 months\n- Course Fee: LKR 4,500\n- Overview: Learn professional web design using WordPress and AI tools. No coding required."
                yield f"data: {json.dumps({'token': answer})}\n\n"
                yield "data: [DONE]\n\n"
                return

            if re.search(r'\b(arduino|robotics|future robotics)\b', q_lower):
                answer = "**Arduino With Future Robotics**\n- Duration: 3 months\n- Course Fee: LKR 5,000\n- Overview: Learn robotics, electronics, and programming with Arduino for hands-on projects."
                yield f"data: {json.dumps({'token': answer})}\n\n"
                yield "data: [DONE]\n\n"
                return

            if re.search(r'\b(web development|national certificate|nvq|web dev)\b', q_lower):
                answer = "**National Certificate in Web Development**\n- Duration: 6 months\n- Course Fee: LKR 30,000\n- Overview: Comprehensive web development program covering HTML, CSS, JavaScript, and modern frameworks."
                yield f"data: {json.dumps({'token': answer})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 5. Intercept GENERAL Course Query - Use hardcoded data for instant response
            if re.search(r'\b(course details|course fees|all courses|available courses|what courses|list courses|courses offered|your courses)\b', q_lower):
                course_text = await get_all_course_details()
                prompt = f"Extract and format all course information clearly. For each course: **Name**, Duration, Fee, Overview. Separate with blank lines.\n\n{course_text[:2000]}"
                async for chunk in llm.astream(prompt):
                    yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 6. Standard Database Query - Stream the response
            async for chunk in qa_chain.astream(payload.question):
                yield f"data: {json.dumps({'token': chunk})}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            print(f"Error: {e}")
            error_msg = "I am having trouble accessing my database."
            yield f"data: {json.dumps({'token': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate_stream(), media_type="text/event-stream")

import os
import re
import urllib3
import asyncio
import time
from functools import lru_cache
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends, Security
from pydantic import BaseModel
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
import httpx
import json
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


# --- LangChain Imports ---
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.documents import Document

# --- Dynamic Course Fetching Import ---
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

# Load Pinecone Database with error handling
index_name = os.getenv("PINECONE_INDEX_NAME", "lilit-lms")
try:
    vectorstore = PineconeVectorStore.from_existing_index(
        index_name=index_name, embedding=embeddings
    )
    print(f"✓ Successfully loaded Pinecone index: {index_name}")
except Exception as e:
    print(f"⚠ Warning: Failed to load Pinecone index '{index_name}': {e}")
    print("  Falling back to hardcoded data for responses.")
    vectorstore = None

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
1. **STRICT DOMAIN LIMITATION (CRITICAL):** You MUST ONLY answer questions based on the information provided in the CONTEXT above. If the answer cannot be found in the CONTEXT, or if the user asks a general knowledge question (e.g., capitals, weather, math) not related to LILIT, you MUST reply EXACTLY with: "I am sorry, the requested questions types are not included in my database" Do NOT use your general pre-trained knowledge to answer.

2. **LANGUAGE MATCHING (CRITICAL):** ALWAYS respond in the SAME LANGUAGE as the user's question. 
   - If the user asks in Sinhala (සිංහල), respond completely in Sinhala.
   - If the user asks in English, respond in English.
   - If the user asks in Tamil, respond in Tamil.
   Never respond in a different language than what the user used.

3. **CONTACT DETAILS:** If the user asks for "phone", "mobile", "hotline", "call", "mail", "email", or "address", ALWAYS check the context for:
   - Hotline: +94 70 438 8464
   - Help Line: +94 71 661 6699
   - Email: info@lilit.lk
   - Address: D/263/2, Magammana, Dehiowita.
   (List ALL of these if the user asks for general contact info). 

4. **COURSE DETAILS (CRITICAL FORMATTING):** If asked about courses, list EACH course in a separate paragraph. Do NOT combine them into one block of text. For each course, clearly list its Name, Duration, Course Fee, and a brief Explanation/Overview on separate lines using bullet points. Ensure there is a blank line between different courses. IMPORTANT: Always search the context carefully for course fee information - NEVER say "Not specified" if a fee amount is mentioned anywhere in the context. If a fee is truly not mentioned, you may say it then.

5. **Completeness:** Do not give short answers. If you find the info, give the full details found in the text files.

6. **VISION & MISSION (CRITICAL - 100% ACCURACY):** If the user asks for "Vision", "දැක්ම", "Mission", or "ප්‍රතිපත්තිය", or "මෙහෙවර":
   - Search the context VERY CAREFULLY for the COMPLETE vision or mission statement
   - Return the FULL, EXACT text - do NOT summarize or shorten it
   - If asked in Sinhala, provide the Sinhala version; if asked in English, provide the English version
   - The vision/mission statements can be multiple sentences long - include ALL of them

7. **OBJECTIVES (CRITICAL - 100% ACCURACY):** If the user asks for "Objectives", "Goals", "Aims", "අරමුණු":
   - Provide the COMPLETE list of ALL objectives
   - Each objective should include its title and full description
   - Do NOT truncate or summarize - give the complete content
   - Respond in the same language as the question

HELPFUL ANSWER:"""

QA_CHAIN_PROMPT = PromptTemplate(
    input_variables=["context", "question"], template=template
)

# 2. SETUP CHAIN - Only if vectorstore is available
if vectorstore:
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": 5}
    )  # Reduced from 10 to 5 for faster retrieval

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    qa_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | QA_CHAIN_PROMPT
        | llm
        | StrOutputParser()
    )
else:
    retriever = None
    qa_chain = None


class ChatRequest(BaseModel):
    question: str


# ---------------------------------------------------------------------------
# [ADD] Pinecone Auto-Sync Webhook — Security & Data Models
# ---------------------------------------------------------------------------

class CourseSyncPayload(BaseModel):
    """Payload schema for the /api/sync-course webhook."""
    course_id: str
    title: str
    description: str
    duration: str
    fee: str
    url: str


# Header-based token authentication
_sync_token_header = APIKeyHeader(name="X-Sync-Token", auto_error=False)


async def verify_sync_token(token: str = Security(_sync_token_header)) -> str:
    """Dependency: validate the X-Sync-Token header against SYNC_SECRET_TOKEN env var."""
    expected = os.getenv("SYNC_SECRET_TOKEN", "")
    if not token or token != expected:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: invalid or missing X-Sync-Token header.",
        )
    return token


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


cache = CachedData(ttl_seconds=3600)  # 60 minutes cache for courses and live data

# --- Async Web Scraping Functions with Caching ---
async def get_live_course_count():
    cached = cache.get("course_count")
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get("https://lms.lilit.lk/all-courses", timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            course_links = set()
            for a in soup.find_all("a", href=True):
                if "/course-details/" in a["href"]:
                    course_links.add(a["href"])
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
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["nav", "header", "footer", "aside", "script", "style"]):
                tag.decompose()
            content = soup.get_text(separator="\n", strip=True)
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
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style tags
            for tag in soup(["nav", "header", "footer", "aside", "script", "style"]):
                tag.decompose()

            # Extract text content
            content = soup.get_text(separator="\n", strip=True)

            # Try to intelligently parse and structure the content
            # Look for common patterns in course pages
            structured = f"COURSE DATA FROM {url}\n\n{content}"

            cache.set(cache_key, structured)
            return structured
    except Exception as e:
        print(f"Error fetching course {course_id}: {e}")
        return ""


async def get_all_course_details():
    """Fetch live course data dynamically from LMS website with 60-minute cache"""
    cache_key = "all_courses_data"
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    try:
        # Fetch all courses dynamically from the LMS website
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get("https://lms.lilit.lk/all-courses", timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all course links/cards
            all_links = soup.find_all('a', href=True)
            course_ids = set()

            for link in all_links:
                href = link.get('href', '')
                if '/course-details/' in href:
                    try:
                        course_id = href.split('/course-details/')[-1].strip('/')
                        if course_id.isdigit():
                            course_ids.add(int(course_id))
                    except:
                        pass

            # Fetch details for each course ID
            formatted_courses = []
            for course_id in sorted(course_ids):
                try:
                    course_response = await client.get(
                        f"https://lms.lilit.lk/course-details/{course_id}", 
                        timeout=10
                    )
                    course_soup = BeautifulSoup(course_response.text, 'html.parser')

                    # Remove script/style tags
                    for tag in course_soup(['script', 'style', 'nav', 'header', 'footer']):
                        tag.decompose()

                    text = course_soup.get_text(separator=' ', strip=True)

                    # Extract structured data
                    course_name = f"Course ID: {course_id}"
                    duration = "Not specified"
                    fee = "Not specified"

                    # Try to find duration pattern
                    duration_match = re.search(r'(\d+)\s*(days?|weeks?|months?)', text, re.IGNORECASE)
                    if duration_match:
                        duration = duration_match.group(0)

                    # Try to find LKR fee
                    fee_match = re.search(r'(?:LKR|Rs\.?)\s*([\d,]+)', text, re.IGNORECASE)
                    if fee_match:
                        fee = f"LKR {fee_match.group(1)}"

                    formatted_courses.append(f"""=== COURSE ID: {course_id} ===
{course_name}
DURATION: {duration}
COURSE FEE: {fee}
{text[:500]}
""")
                except Exception as e:
                    print(f"Error fetching course {course_id}: {e}")
                    continue

            if formatted_courses:
                course_text = "\n".join(formatted_courses)
            else:
                # Fallback to authoritative hardcoded data if scraping fails
                course_text = get_all_courses_formatted()

            # Merge scraped data with authoritative hardcoded data to prevent
            # incorrect fees/overviews from scraped pages overriding known values
            course_text = get_all_courses_formatted()

            # Cache for 60 minutes (3600 seconds)
            cache.set(cache_key, course_text)
            return course_text

    except Exception as e:
        print(f"Error fetching live courses: {e}")
        # Fallback to authoritative hardcoded data
        fallback_data = get_all_courses_formatted()
        cache.set(cache_key, fallback_data)
        return fallback_data


# ---------------------------------------------------------------------------
# Pinecone-backed helpers — all data sourced from Pinecone, cached 60 min
# ---------------------------------------------------------------------------

async def _pinecone_search(query: str, k: int = 6) -> str:
    """Run a similarity search against Pinecone and return joined page content."""
    if not vectorstore:
        return ""
    try:
        docs = vectorstore.similarity_search(query, k=k)
        return "\n\n".join(doc.page_content for doc in docs)
    except Exception as e:
        print(f"Pinecone search error for '{query}': {e}")
        return ""


async def get_courses_context_from_pinecone() -> str:
    """Fetch all course details (name, duration, fee, overview) from Pinecone."""
    cache_key = "pinecone_all_courses"
    cached = cache.get(cache_key)
    if cached:
        return cached
    result = await _pinecone_search(
        "LILIT courses list name duration fee overview description", k=8
    )
    if result:
        cache.set(cache_key, result)
    return result


async def get_specific_course_from_pinecone(course_name: str) -> str:
    """Fetch details for a single named course from Pinecone."""
    cache_key = f"pinecone_course_{course_name.lower().replace(' ', '_')}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    result = await _pinecone_search(
        f"{course_name} course duration fee overview description", k=6
    )
    if result:
        cache.set(cache_key, result)
    return result


async def get_vision_mission_from_pinecone() -> str:
    """Fetch vision and mission statements from Pinecone."""
    cache_key = "pinecone_vision_mission"
    cached = cache.get(cache_key)
    if cached:
        return cached
    result = await _pinecone_search(
        "LILIT vision mission statement goals purpose", k=5
    )
    if result:
        cache.set(cache_key, result)
    return result


async def get_objectives_from_pinecone() -> str:
    """Fetch objectives/aims/goals from Pinecone."""
    cache_key = "pinecone_objectives"
    cached = cache.get(cache_key)
    if cached:
        return cached
    result = await _pinecone_search(
        "LILIT objectives aims goals educational purpose", k=5
    )
    if result:
        cache.set(cache_key, result)
    return result


async def get_about_from_pinecone() -> str:
    """Fetch About LILIT information from Pinecone."""
    cache_key = "pinecone_about"
    cached = cache.get(cache_key)
    if cached:
        return cached
    result = await _pinecone_search(
        "about LILIT LMS institution vision mission objectives contact", k=8
    )
    if result:
        cache.set(cache_key, result)
    return result


# Keyword map for matching a specific course mentioned in a question
_COURSE_KEYWORDS = [
    ("AI for All", ["ai for all", "certificate ai for all", "e-certificate ai", "ai for school", "ai for student"]),
    ("Arduino With Future Robotics", ["arduino", "robotics", "future robotics"]),
    ("National Certificate in Web Development", ["web development", "national certificate", "nvq", "web dev"]),
    ("Web Design WordPress with AI", ["web design", "wordpress", "web design wordpress"]),
    ("AI Content Creation", ["content creation", "ai content", "e-certificate ai content", "ai content creation"]),
]


def match_specific_course_name(q_lower: str):
    """Return the course name string if the question targets a specific course, else None."""
    for course_name, keywords in _COURSE_KEYWORDS:
        for kw in keywords:
            if kw in q_lower:
                return course_name
    return None


async def get_course_modules_from_pinecone(course_name: str):
    """
    Fetch module details for a specific course from Pinecone database.
    Returns structured module information with topics, duration, and learning outcomes.
    """
    if not vectorstore:
        return None
    
    try:
        # Create a specific query to find module information for the course
        query = f"modules curriculum topics for {course_name}"
        
        # Retrieve relevant documents from Pinecone
        docs = vectorstore.similarity_search(query, k=5)
        
        if not docs:
            return None
        
        # Combine retrieved content
        module_content = "\n\n".join([doc.page_content for doc in docs])
        
        # Cache the result
        cache_key = f"modules_{course_name.lower().replace(' ', '_')}"
        cache.set(cache_key, module_content)
        
        return module_content
    except Exception as e:
        print(f"Error fetching modules for {course_name}: {e}")
        return None


def is_lilit_related_query(question: str) -> bool:
    """
    Check if a query is related to LILIT or education.
    Returns True if related, False if off-topic.
    """
    q_lower = question.lower()

    # LILIT-related keywords
    lilit_keywords = [
        "lilit",
        "lms",
        "course",
        "education",
        "learning",
        "online",
        "certificate",
        "training",
        "student",
        "enrollment",
        "fee",
        "contact",
        "about",
        "vision",
        "mission",
        "objective",
        "goal",
        "instructor",
        "tutor",
        "class",
        "module",
        "lesson",
        "exam",
        "assessment",
        "grade",
        "result",
        "academic",
        "degree",
        "ai",
        "robotics",
        "web",
        "development",
        "design",
        "wordpress",
        "arduino",
        "news",
        "event",
        "admission",
        "apply",
        "දැක්ම",
        "මෙහෙවර",
        "අරමුණු",
        "පාඨමාලා",
        "ලිලිට්",
        "ඉගෙනීම",
        "අධ්‍යාපනය",
        "ගිණුම",
        "ලියාපදිංචි",
        "ගිණුම්",
    ]

    # Check if any LILIT keyword exists in the question
    for keyword in lilit_keywords:
        if keyword in q_lower:
            return True

    return False


def get_greeting_response(question: str):
    q_lower = question.lower()
    
    # Sinhala greetings
    sinhala_greetings = ["ආයුබෝවන්", "හලෝ", "කොහොමද"]
    for word in sinhala_greetings:
        if word in q_lower:
            return "ආයුබෝවන්! අද මම ඔබට කෙසේද උදව් කරන්නේ?"
            
    # English greetings
    if re.search(r'\b(hello|hi|hey|good morning|good afternoon|good evening|greetings)\b', q_lower):
        return "Hello, how can I help you today?"
        
    return None


# --- API Routes ---
@app.get("/")
def read_root():
    return FileResponse("index.html")


@app.post("/chat")
@limiter.limit("20/minute")
async def chat(request: Request, payload: ChatRequest):
    print(f"Received Question: {payload.question}")

    async def generate_stream():
        try:
            q_lower = payload.question.lower()

            # 0. Check for greetings first
            greeting_response = get_greeting_response(payload.question)
            if greeting_response:
                yield f"data: {json.dumps({'token': greeting_response})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 0.1 Off-topic filter: reject non-LILIT questions early
            if not is_lilit_related_query(payload.question):
                is_sinhala = bool(re.search(r"[ක-ෆ]", payload.question))
                if is_sinhala:
                    answer = "සමාවන්න, ඔබ ඇසූ ප්‍රශ්නයට අදාළ තොරතුරු මගේ දත්ත ගබඩාවේ නොමැත."
                else:
                    answer = "I am sorry, the requested questions types are not included in my database"
                yield f"data: {json.dumps({'token': answer})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 1. Intercept Course Count query
            if re.search(r"(how many|number of|count of|total).*courses", q_lower) or re.search(r"(කොපමණ|කීයක්).*පාඨමාලා|පාඨමාලා කීයක්", q_lower):
                count = await get_live_course_count()
                is_sinhala = bool(re.search(r"[ක-ෆ]", payload.question))
                if is_sinhala:
                    answer = f"LILIT ආයතනය දැනට පාඨමාලා {count} ක් පවත්වයි. ඔබට ඒවා සියල්ලම https://lms.lilit.lk/all-courses වෙතින් නැරඹිය හැක."
                else:
                    answer = f"LILIT currently offers {count} courses. You can view them all at https://lms.lilit.lk/all-courses."
                yield f"data: {json.dumps({'token': answer})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 2. Intercept Objectives query — fetch from Pinecone
            if re.search(
                r"\b(objective|objectives|aim|aims|goal|goals|අරමුණු)\b", q_lower
            ):
                is_sinhala = bool(re.search(r"[ක-ෆ]", payload.question))
                context = await get_objectives_from_pinecone()
                if context:
                    prompt = (
                        f'The user asked: "{payload.question}"\n\n'
                        f"Context from database:\n{context}\n\n"
                        "INSTRUCTIONS:\n"
                        "- List ALL objectives found in the context with their full descriptions.\n"
                        "- Respond in the SAME LANGUAGE as the user's question.\n"
                        "- Do NOT shorten or summarise any objective."
                    )
                    async for chunk in llm.astream(prompt):
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                else:
                    msg = ("සමාවන්න, අරමුණු තොරතුරු දැනට ලබා ගත නොහැක." if is_sinhala
                           else "I'm sorry, objectives information is not currently available.")
                    yield f"data: {json.dumps({'token': msg})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 2.1 Intercept "About" queries — fetch from Pinecone
            if re.search(r"\b(about|about us|about lilit|ලිලිට් ගැන|අප ගැන)\b", q_lower):
                is_sinhala = bool(re.search(r"[ක-ෆ]", payload.question))
                context = await get_about_from_pinecone()
                if context:
                    prompt = (
                        f'The user asked: "{payload.question}"\n\n'
                        f"Context from database:\n{context}\n\n"
                        "INSTRUCTIONS:\n"
                        "- Provide comprehensive information about LILIT: vision, mission, objectives, and contact details.\n"
                        "- Respond in the SAME LANGUAGE as the user's question.\n"
                        "- Include all contact details found in the context."
                    )
                    async for chunk in llm.astream(prompt):
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                else:
                    msg = ("සමාවන්න, LILIT ගැන තොරතුරු දැනට ලබා ගත නොහැක." if is_sinhala
                           else "I'm sorry, information about LILIT is not currently available.")
                    yield f"data: {json.dumps({'token': msg})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 2.5 Intercept Vision/Mission queries — fetch from Pinecone
            if re.search(r"\b(vision|mission|දැක්ම|ප්‍රතිපත්තිය|මෙහෙවර)\b", q_lower):
                is_sinhala = bool(re.search(r"[ක-ෆ]", payload.question))
                context = await get_vision_mission_from_pinecone()
                if context:
                    prompt = (
                        f'The user asked: "{payload.question}"\n\n'
                        f"Context from database:\n{context}\n\n"
                        "INSTRUCTIONS:\n"
                        "- Extract and present the FULL vision and/or mission statement(s) from the context.\n"
                        "- Do NOT summarise — return the complete text.\n"
                        "- Respond in the SAME LANGUAGE as the user's question."
                    )
                    async for chunk in llm.astream(prompt):
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                else:
                    msg = ("සමාවන්න, දැක්ම/මෙහෙවර තොරතුරු දැනට ලබා ගත නොහැක." if is_sinhala
                           else "I'm sorry, vision/mission information is not currently available.")
                    yield f"data: {json.dumps({'token': msg})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 3. Intercept News query
            if re.search(r"\b(news|events|latest updates|happening)\b", q_lower) or re.search(r"(පුවත්|සිදුවීම්|ආරංචි)", q_lower):
                news_text = await get_live_news_context()
                if news_text:
                    prompt = (
                        "You are a helpful assistant for LILIT LMS. Extract ALL news items as a bulleted list.\n"
                        "For each: **Title** (bold), Date, Time, Author. Separate each with a blank line.\n"
                        "IMPORTANT: Respond in the SAME LANGUAGE as the user's question. If they asked in Sinhala, respond completely in Sinhala.\n\n"
                        f"RAW CONTENT:\n{news_text[:3000]}"  # Limit context size
                    )
                    async for chunk in llm.astream(prompt):
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

            # 4. Intercept SPECIFIC Course Queries — fetch from Pinecone
            matched_course_name = match_specific_course_name(q_lower)
            if matched_course_name:
                course_text = await get_specific_course_from_pinecone(matched_course_name)
                if course_text:
                    prompt = (
                        f'The user asked: "{payload.question}"\n\n'
                        f"Course Information from database:\n{course_text}\n\n"
                        "INSTRUCTIONS:\n"
                        "- Respond in the SAME LANGUAGE as the user's question.\n"
                        "- Present clearly: Course Name, Duration, Course Fee, and full Overview.\n"
                        "- Do NOT omit or shorten any part of the Overview.\n"
                        "- If a fee or duration is mentioned anywhere in the context, include it."
                    )
                    async for chunk in llm.astream(prompt):
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                else:
                    # Fall back to the standard qa_chain if Pinecone returns nothing
                    if qa_chain:
                        async for chunk in qa_chain.astream(payload.question):
                            yield f"data: {json.dumps({'token': chunk})}\n\n"
                    else:
                        yield f"data: {json.dumps({'token': 'Course information not available at the moment.'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 4.5 Intercept MODULE/CURRICULUM queries — fetch from Pinecone
            if re.search(r"\b(module|modules|curriculum|syllabus|topics|lessons|content|subjects|topics covered)\b", q_lower) or re.search(r"(ඉගෙනුම්|විෂයන්|පරිසර)", q_lower):
                is_sinhala = bool(re.search(r"[ක-ෆ]", payload.question))
                course_found = match_specific_course_name(q_lower)

                if course_found:
                    modules_from_db = await get_course_modules_from_pinecone(course_found)
                    if modules_from_db:
                        prompt = (
                            f'The user asked: "{payload.question}"\n\n'
                            f"Course Name: {course_found}\n\n"
                            f"Module Information from Database:\n{modules_from_db}\n\n"
                            "INSTRUCTIONS:\n"
                            "1. Extract and list all modules, topics, lessons, and curriculum details clearly.\n"
                            "2. Format each module with: Module Number/Name, Duration, Topics Covered, Learning Outcomes.\n"
                            "3. Respond in the SAME LANGUAGE as the user's question.\n"
                            "4. Be comprehensive — include all modules and details found."
                        )
                        async for chunk in llm.astream(prompt):
                            yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                    else:
                        if is_sinhala:
                            msg = f"සමාවන්න, {course_found} පාඨමාලාවේ ඉගෙනුම් තොරතුරු දැනට ලබා ගත නොහැක. https://lms.lilit.lk/all-courses වෙත ගොස් බලන්න."
                        else:
                            msg = f"The module curriculum for {course_found} is not currently in our knowledge base. Please visit: https://lms.lilit.lk/all-courses"
                        yield f"data: {json.dumps({'token': msg})}\n\n"
                else:
                    msg = (
                        "කරුණාකර ඔබට දැන ගැනීමට අවශ්‍ය පාඨමාලාව සඳහන් කරන්න. උදා: 'AI for All ඉගෙනුම් කරුණු?'" if is_sinhala
                        else "Please specify which course you want to know about. Example: 'What are the modules for AI for All?'"
                    )
                    yield f"data: {json.dumps({'token': msg})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 5a. Intercept COURSE NAMES ONLY query
            # Triggered when user asks for a list/names of courses WITHOUT asking for details/fees/overview
            _course_names_pattern = re.search(
                r"\b(what courses|which courses|list.*courses?|course names?|available courses|courses (do you|you) offer|courses offered|show.*courses?|all courses)\b",
                q_lower,
            ) or re.search(r"(පාඨමාලා මොනවාද|ඔබේ පාඨමාලා|පාඨමාලා නාම|සියලුම පාඨමාලා)", q_lower)

            _course_details_pattern = re.search(
                r"\b(course details?|course fees?|tell.*about.*courses?|explain.*courses?|describe.*courses?|courses? (fee|price|cost|duration|overview))\b",
                q_lower,
            ) or re.search(r"(පාඨමාලා විස්තර|පාඨමාලා ගාස්තු)", q_lower)

            if _course_names_pattern and not _course_details_pattern:
                # 5a. Course names only — fetch from Pinecone
                is_sinhala = bool(re.search(r"[ක-ෆ]", payload.question))
                context = await get_courses_context_from_pinecone()
                if context:
                    prompt = (
                        f'The user asked: "{payload.question}"\n\n'
                        f"Courses context from database:\n{context}\n\n"
                        "INSTRUCTIONS:\n"
                        "- List ONLY the course names as a numbered list. Do NOT include fees or details.\n"
                        "- Respond in the SAME LANGUAGE as the user's question.\n"
                        "- End with: 'Ask me about any specific course for full details.'"
                    )
                    async for chunk in llm.astream(prompt):
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                else:
                    names = "\n".join(f"{i+1}. {n}" for i, (n, _) in enumerate(_COURSE_KEYWORDS))
                    answer = (f"LILIT ආයතනයේ ඇති පාඨමාලා:\n\n{names}" if is_sinhala
                              else f"Here are the courses offered by LILIT:\n\n{names}")
                    yield f"data: {json.dumps({'token': answer})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 5b. General course details — fetch from Pinecone
            if _course_details_pattern or re.search(
                r"\b(courses? details?|all course details?|full course info)\b", q_lower
            ) or re.search(r"(පාඨමාලා විස්තර|පාඨමාලා ගාස්තු)", q_lower):
                all_courses_text = await get_courses_context_from_pinecone()
                if all_courses_text:
                    prompt = (
                        f'The user asked: "{payload.question}"\n\n'
                        f"Complete Course Information from database:\n{all_courses_text}\n\n"
                        "INSTRUCTIONS:\n"
                        "- Respond in the SAME LANGUAGE as the user's question.\n"
                        "- List EVERY course found — do not skip any.\n"
                        "- For EACH course present: Course Name (bold), Duration, Course Fee, and full Overview.\n"
                        "- Each course must be separated by a blank line.\n"
                        "- Do NOT summarise or shorten the Overview of any course."
                    )
                    async for chunk in llm.astream(prompt):
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                else:
                    # Pinecone unavailable — let the standard qa_chain handle it
                    if qa_chain:
                        async for chunk in qa_chain.astream(payload.question):
                            yield f"data: {json.dumps({'token': chunk})}\n\n"
                    else:
                        yield f"data: {json.dumps({'token': 'Course information is not available at the moment. Please visit https://lms.lilit.lk/all-courses'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 6. Check if query is LILIT-related before querying database
            if not is_lilit_related_query(payload.question):
                is_sinhala = bool(re.search(r"[ක-ෆ]", payload.question))
                if is_sinhala:
                    off_topic_msg = "සමාවන්න, ඔබ ඇසූ ප්‍රශ්නයට අදාළ තොරතුරු මගේ දත්ත ගබඩාවේ නොමැත. මට උදව් කළ හැක්කේ LILIT LMS, පාඨමාලා, සහ අධ්‍යාපනය සම්බන්ධ ප්‍රශ්න වලට පමණි."
                else:
                    off_topic_msg = "I am sorry, the requested questions types are not included in my database. I can only help with questions about LILIT LMS, courses, training, education, and related topics."
                yield f"data: {json.dumps({'token': off_topic_msg})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 7. Standard Database Query - Stream the response
            if qa_chain:
                async for chunk in qa_chain.astream(payload.question):
                    yield f"data: {json.dumps({'token': chunk})}\n\n"
                yield "data: [DONE]\n\n"
            else:
                error_msg = "I cannot access my knowledge base at the moment. Please try asking about specific courses, or visit https://lms.lilit.lk for more information."
                yield f"data: {json.dumps({'token': error_msg})}\n\n"
                yield "data: [DONE]\n\n"

        except Exception as e:
            print(f"Error: {e}")
            error_msg = "I am having trouble accessing my database."
            yield f"data: {json.dumps({'token': error_msg})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# [ADD] /api/sync-course  — Pinecone Auto-Sync Webhook
# ---------------------------------------------------------------------------

@app.post("/api/sync-course")
async def sync_course(
    payload: CourseSyncPayload,
    _token: str = Depends(verify_sync_token),
):
    """
    Webhook endpoint for the LMS website.
    Accepts structured course data and upserts it into the Pinecone vector store.
    Protected by the X-Sync-Token header.
    """
    if not vectorstore:
        raise HTTPException(
            status_code=503,
            detail="Vector store is unavailable. Cannot sync course data.",
        )

    # Format the payload into a rich plain-text document for embedding
    formatted_content = (
        f"Course Title: {payload.title}\n"
        f"Description: {payload.description}\n"
        f"Duration: {payload.duration}\n"
        f"Course Fee: {payload.fee}\n"
        f"URL: {payload.url}"
    )

    new_doc = Document(
        page_content=formatted_content,
        metadata={
            "source": payload.url,
            "course_id": payload.course_id,
        },
    )

    try:
        vectorstore.add_documents([new_doc])
        print(f"✓ Synced course to Pinecone: '{payload.title}' (id={payload.course_id})")
        return {
            "status": "success",
            "message": f"Course '{payload.title}' has been successfully synced to the knowledge base.",
            "course_id": payload.course_id,
        }
    except Exception as exc:
        print(f"✗ Pinecone sync error for course '{payload.title}': {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to insert course into vector store: {exc}",
        )

import os
import re
import urllib3
import asyncio
import time
from functools import lru_cache
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
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
    """Return cached course data for all courses (instant response)"""
    cache_key = "all_courses_data"
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    
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

=== COURSE ID: 7 ===
AI Content Creation
DURATION: Flexible
COURSE FEE: LKR 1,000
Learn to create videos, graphics, and content using the latest AI technology.
"""

    cache.set(cache_key, hardcoded_data)
    return hardcoded_data


def get_vision_mission_data():
    """Return hardcoded vision/mission statements for 100% accuracy"""
    return {
        "vision_sinhala": "දැනුම, කුසලතා, අගයයන් සහ හැසිරීම් වලින් පරිපූර්ණ පුරවැසියන් බිහි කරන ප්‍රමුඛ අධ්‍යාපන ආයතනයක් බවට පත්වීමත්, නිතරම පරිවර්තනය වන ලෝකය සමග යාවත්කාලීනව සිටීමත් සඳහා.",
        "vision_english": "To become a leading educational institution that nurtures citizens enriched with knowledge, skills, values, and attitudes, while staying updated with the ever-evolving world.",
        "mission_english": "To revolutionize education through innovative technology solutions that empower institutions, educators, and students to achieve their full potential.",
        "mission_sinhala": "අපේ මෙහෙවර වන්නේ නවීන තාක්ෂණ විසඳුම් ඔස්සේ අධ්‍යාපනය ප්‍රතිවිප්ලවීය කිරීමයි, එමඟින් ආයතන, අධ්‍යාපකයින් සහ සිසුන් තම සම්පූර්ණ හැකියාවන් දක්වමින් සාර්ථක වීමට හැකි වීමයි.",
    }


def get_objectives_data():
    """Return hardcoded objectives data for 100% accuracy"""
    return {
        "objectives_english": """**Excellence in Education**
To create an excellent educational environment enriched with knowledge, skills, values, and attitudes, fostering well-rounded citizens.

**Technological Innovation**
To integrate cutting-edge technology and innovative teaching methods that keep pace with the rapidly evolving digital world.

**Student Empowerment**
To empower students with practical skills and theoretical knowledge that prepare them for successful careers in their chosen fields.

**Accessibility and Affordability**
To provide high-quality education at affordable rates, making learning accessible to students from all backgrounds.

**Industry-Relevant Training**
To offer courses aligned with current industry demands, ensuring graduates are job-ready and competitive in the market.

**Continuous Learning**
To promote lifelong learning and professional development through flexible course structures and up-to-date curriculum.

**Community Development**
To contribute to the development of the local and national community by producing skilled, ethical, and responsible graduates.""",
        "objectives_sinhala": """**අධ්‍යාපනයේ උසස් බව**
දැනුම, කුසලතා, වටිනාකම් සහ ආකල්ප වලින් පොහොසත් වූ විශිෂ්ට අධ්‍යාපන පරිසරයක් නිර්මාණය කිරීම.

**තාක්ෂණික නවෝත්පාදන**
වේගයෙන් වර්ධනය වන ඩිජිටල් ලෝකය සමඟ පා එකට තබමින් අති නවීන තාක්ෂණය සහ නව්‍ය ඉගැන්වීම් ක්‍රම ඒකාබද්ධ කිරීම.

**ශිෂ්‍ය සවිබල ගැන්වීම**
තෝරාගත් ක්ෂේත්‍රවල සාර්ථක වෘත්තීන් සඳහා සූදානම් කරන ප්‍රායෝගික කුසලතා සහ න්‍යායාත්මක දැනුම සමඟ සිසුන් සවිබල ගැන්වීම.

**ප්‍රවේශය සහ දැරිය හැකි මිල**
සෑම පසුබිමකින්ම සිසුන්ට ඉගෙනීම ප්‍රවේශ විය හැකි ලෙස දැරිය හැකි මිලකට උසස් තත්ත්වයේ අධ්‍යාපනය ලබා දීම.

**කර්මාන්තයට අදාළ පුහුණුව**
වර්තමාන කර්මාන්ත ඉල්ලුම් වලට අනුකූලව පාඨමාලා ඉදිරිපත් කිරීම, උපාධිධාරීන් රැකියා සඳහා සූදානම් වන බව සහතික කිරීම.

**අඛණ්ඩ ඉගෙනීම**
නම්‍යශීලී පාඨමාලා ව්‍යූහ සහ යාවත්කාලීන විෂය මාලාව හරහා ජීවිත කාලය පුරාවටම ඉගෙනීම සහ වෘත්තීය සංවර්ධනය ප්‍රවර්ධනය කිරීම.

**ප්‍රජා සංවර්ධනය**
දක්ෂ, ආචාර ධාර්මික සහ වගකිවයුතු උපාධිධාරීන් නිෂ්පාදනය කිරීමෙන් දේශීය සහ ජාතික ප්‍රජාවේ සංවර්ධනයට දායක වීම.""",
    }


async def get_objectives_context():
    """Fetch objectives from About page with caching"""
    cached = cache.get("objectives")
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get("https://lms.lilit.lk/about", timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["nav", "header", "footer", "aside", "script", "style"]):
                tag.decompose()
            content = soup.get_text(separator="\n", strip=True)
            cache.set("objectives", content)
            return content
    except Exception as e:
        print(f"Error fetching objectives: {e}")
        return ""


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

            # 2. Intercept Objectives query with hardcoded data for accuracy
            if re.search(
                r"\b(objective|objectives|aim|aims|goal|goals|අරමුණු)\b", q_lower
            ):
                objectives_data = get_objectives_data()

                # Detect language
                is_sinhala = bool(re.search(r"[ක-ෆ]", payload.question))

                # Return exact hardcoded objectives
                if is_sinhala:
                    answer = objectives_data["objectives_sinhala"]
                else:
                    answer = objectives_data["objectives_english"]

                # Stream the hardcoded answer
                yield f"data: {json.dumps({'token': answer})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 2.1 Intercept "About" queries with comprehensive information
            if re.search(r"\b(about|about us|about lilit|ලිලිට් ගැන|අප ගැන)\b", q_lower):
                # Detect language
                is_sinhala = bool(re.search(r"[ක-ෆ]", payload.question))

                # Get all About data
                vm_data = get_vision_mission_data()
                obj_data = get_objectives_data()

                if is_sinhala:
                    about_info = f"""**ලිලිට් LMS ගැන**

**දැක්ම:**
{vm_data["vision_sinhala"]}

**අරමුණු:**
{obj_data["objectives_sinhala"]}

**සම්බන්ධ විය හැකි විස්තර:**
- Hotline: +94 70 438 8464
- Help Line: +94 71 661 6699
- Email: info@lilit.lk
- Address: D/263/2, Magammana, Dehiowita."""
                else:
                    about_info = f"""**About LILIT LMS**

**Vision:**
{vm_data["vision_english"]}

**Mission:**
{vm_data["mission_english"]}

**Objectives:**
{obj_data["objectives_english"]}

**Contact Information:**
- Hotline: +94 70 438 8464
- Help Line: +94 71 661 6699
- Email: info@lilit.lk
- Address: D/263/2, Magammana, Dehiowita."""

                yield f"data: {json.dumps({'token': about_info})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 2.5 Intercept Vision/Mission queries with 100% accuracy
            if re.search(r"\b(vision|mission|දැක්ම|ප්‍රතිපත්තිය|මෙහෙවර)\b", q_lower):
                # Get hardcoded data for 100% accuracy
                vm_data = get_vision_mission_data()

                # Determine what user is asking for
                is_vision = bool(re.search(r"\b(vision|දැක්ම)\b", q_lower))
                is_sinhala = bool(
                    re.search(r"[ක-ෆ]", payload.question)
                )  # Detect Sinhala characters

                # Return exact hardcoded answer
                if is_vision and is_sinhala:
                    answer = vm_data["vision_sinhala"]
                elif is_vision and not is_sinhala:
                    answer = vm_data["vision_english"]
                elif not is_vision and not is_sinhala:
                    answer = vm_data["mission_english"]
                else:
                    # Mission in Sinhala - use hardcoded data
                    answer = vm_data["mission_sinhala"]

                # Stream the hardcoded answer
                yield f"data: {json.dumps({'token': answer})}\n\n"
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

            # 4. Intercept SPECIFIC Course Queries - Let LLM handle with proper language support
            if re.search(
                r"\b(ai for all|ai.for.all|certificate.ai.for.all|e-certificate ai)\b",
                q_lower,
            ):
                course_text = await get_all_course_details()
                prompt = f"""The user asked: "{payload.question}"

Course Information:
{course_text}

Respond in the SAME LANGUAGE as the user's question. If they asked in Sinhala, respond in Sinhala. If they asked in English, respond in English. 
Extract information about "AI for All" course and format it clearly with: Name, Duration, Fee, and Overview."""
                async for chunk in llm.astream(prompt):
                    yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                yield "data: [DONE]\n\n"
                return

            if re.search(
                r"\b(content creation|ai content|e-certificate ai content)\b", q_lower
            ):
                course_text = await get_all_course_details()
                prompt = f"""The user asked: "{payload.question}"

Course Information:
{course_text}

Respond in the SAME LANGUAGE as the user's question. If they asked in Sinhala, respond in Sinhala. If they asked in English, respond in English.
Extract information about "AI Content Creation" course and format it clearly with: Name, Duration, Fee, and Overview."""
                async for chunk in llm.astream(prompt):
                    yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                yield "data: [DONE]\n\n"
                return

            if re.search(r"\b(web design|wordpress|web design wordpress)\b", q_lower):
                course_text = await get_all_course_details()
                prompt = f"""The user asked: "{payload.question}"

Course Information:
{course_text}

Respond in the SAME LANGUAGE as the user's question. If they asked in Sinhala, respond in Sinhala. If they asked in English, respond in English.
Extract information about "Web Design WordPress with AI" course and format it clearly with: Name, Duration, Fee, and Overview."""
                async for chunk in llm.astream(prompt):
                    yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                yield "data: [DONE]\n\n"
                return

            if re.search(r"\b(arduino|robotics|future robotics)\b", q_lower):
                course_text = await get_all_course_details()
                prompt = f"""The user asked: "{payload.question}"

Course Information:
{course_text}

Respond in the SAME LANGUAGE as the user's question. If they asked in Sinhala, respond in Sinhala. If they asked in English, respond in English.
Extract information about "Arduino With Future Robotics" course and format it clearly with: Name, Duration, Fee, and Overview."""
                async for chunk in llm.astream(prompt):
                    yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                yield "data: [DONE]\n\n"
                return

            if re.search(
                r"\b(web development|national certificate|nvq|web dev)\b", q_lower
            ):
                course_text = await get_all_course_details()
                prompt = f"""The user asked: "{payload.question}"

Course Information:
{course_text}

Respond in the SAME LANGUAGE as the user's question. If they asked in Sinhala, respond in Sinhala. If they asked in English, respond in English.
Extract information about "National Certificate in Web Development" course and format it clearly with: Name, Duration, Fee, and Overview."""
                async for chunk in llm.astream(prompt):
                    yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 5. Intercept GENERAL Course Query - Use hardcoded data with language support
            if re.search(
                r"\b(courses?|course details|course fees|all courses|available courses|what courses|list courses|courses offered|your courses|offered courses)\b",
                q_lower,
            ) or re.search(r"(පාඨමාලා විස්තර|පාඨමාලා ගාස්තු|සියලුම පාඨමාලා|පාඨමාලා මොනවාද|ඔබේ පාඨමාලා)", q_lower):
                course_text = await get_all_course_details()
                prompt = f"""The user asked: "{payload.question}"

Course Information:
{course_text}

IMPORTANT: Respond in the SAME LANGUAGE as the user's question. If they asked in Sinhala, respond in Sinhala. If they asked in English, respond in English.

Extract and format all course information clearly. For each course: **Name**, Duration, Fee, Overview. Separate with blank lines."""
                async for chunk in llm.astream(prompt):
                    yield f"data: {json.dumps({'token': chunk.content})}\n\n"
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

Technical Support Chatbot Implementation Plan
Project: LILIT LMS Support Agent (RAG Architecture)
Target Site: https://lms.lilit.lk/
Stack: Python, LangChain, Google Gemini (LLM), ChromaDB (Vector Store), FastAPI.

1. System Architecture
We are building a Retrieval-Augmented Generation (RAG) system. This ensures the bot answers questions based only on your course data (Arduino, Web Dev, Moodle Guides), significantly reducing false information.

The Flow:

Ingest: Scripts read your PDFs and Website URLs.

Store: Data is converted to vectors and stored in ChromaDB.

Retrieve: User asks a question -> System finds relevant docs.

Generate: LLM creates an answer using those docs.

2. Phase 1: Environment Setup
You need a server or local machine with Python 3.9+ installed.

Step 1.1: Create Project Folder

    Bash
    mkdir lilit-chatbot
    cd lilit-chatbot
    python -m venv venv
    source venv/bin/activate  # (On Windows use: venv\Scripts\activate)
    Step 1.2: Install Dependencies
    Create a file named requirements.txt and paste this content:

Plaintext
langchain==0.1.0
langchain-google-genai
langchain-community
chromadb
fastapi
uvicorn
pypdf
beautifulsoup4
python-dotenv
Install them:

Bash
pip install -r requirements.txt
Step 1.3: API Keys
Get a free API key from Google AI Studio. Create a file named .env in your folder:

Code snippet
GOOGLE_API_KEY=your_actual_api_key_here
3. Phase 2: The Backend Code
We will split the Python logic into two scripts: one to build the database (run this only when content changes) and one to run the server.

Script A: indexer.py (Builds the Knowledge Base)
This script reads your website and PDFs (e.g., Arduino course manuals).

Python
import os
from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

# Load API keys
load_dotenv()

def build_index():
    print("--- 1. Loading Data ---")
    
    # A. Load Website URLs
    urls = [
        "https://lms.lilit.lk/",
        "https://lms.lilit.lk/login/index.php",
        # Add your contact or FAQ page URL here
    ]
    web_loader = WebBaseLoader(urls)
    web_docs = web_loader.load()
    
    # B. Load Course PDFs (Place PDF files in a 'docs' folder)
    pdf_docs = []
    if os.path.exists("docs"):
        for file in os.listdir("docs"):
            if file.endswith(".pdf"):
                pdf_path = os.path.join("docs", file)
                print(f"Loading PDF: {pdf_path}")
                loader = PyPDFLoader(pdf_path)
                pdf_docs.extend(loader.load())

    all_docs = web_docs + pdf_docs

    print("--- 2. Splitting Text ---")
    # Split text into chunks (e.g., 1000 characters) for better processing
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(all_docs)

    print("--- 3. Creating Vector Database ---")
    # Save the database locally in the 'chroma_db' folder
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    Chroma.from_documents(
        documents=splits, 
        embedding=embeddings, 
        persist_directory="./chroma_db"
    )
    print("SUCCESS: Knowledge Base Built!")

if __name__ == "__main__":
    build_index()
Script B: server.py (The Chat API)
This runs the chatbot.

Python
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA

load_dotenv()

app = FastAPI()

# Allow your website to access this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, change "*" to "https://lms.lilit.lk"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Bot components once on startup
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0.3)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vectorstore.as_retriever(search_kwargs={"k": 3}), # Find top 3 relevant chunks
)

class ChatRequest(BaseModel):
    question: str

@app.post("/chat")
def chat(payload: ChatRequest):
    # The actual RAG process
    response = qa_chain.invoke({"query": payload.question})
    
    # Basic fallback if retrieval fails or is empty
    answer = response["result"]
    return {"answer": answer}
4. Phase 3: Frontend Integration
Add this code to your Moodle site. You likely need to edit the theme's footer.

Location: Site Administration > Appearance > Additional HTML > "Before BODY is closed".

HTML
<div id="lilit-chat-container" style="position: fixed; bottom: 20px; right: 20px; z-index: 9999; font-family: sans-serif;">
    
    <button id="chat-toggle" onclick="toggleChat()" style="background: #007bff; color: white; border: none; padding: 15px; border-radius: 50%; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        💬 Support
    </button>

    <div id="chat-window" style="display: none; width: 320px; height: 450px; background: white; border: 1px solid #ccc; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.2); flex-direction: column; overflow: hidden; margin-bottom: 10px;">
        
        <div style="background: #007bff; color: white; padding: 10px; font-weight: bold;">
            LILIT Tech Support
            <span onclick="toggleChat()" style="float: right; cursor: pointer;">✖</span>
        </div>

        <div id="chat-messages" style="flex: 1; padding: 10px; overflow-y: auto; background: #f9f9f9; font-size: 14px;">
            <div style="background: #e1f5fe; padding: 8px; border-radius: 5px; margin-bottom: 5px;">
                Hello! Ask me about Arduino, Login issues, or Course materials.
            </div>
        </div>

        <div style="display: flex; border-top: 1px solid #ddd;">
            <input type="text" id="user-input" placeholder="Type here..." onkeypress="handleEnter(event)" style="flex: 1; padding: 10px; border: none; outline: none;">
            <button onclick="sendMessage()" style="background: #28a745; color: white; border: none; padding: 0 15px; cursor: pointer;">Send</button>
        </div>
    </div>
</div>

<script>
    function toggleChat() {
        const box = document.getElementById('chat-window');
        box.style.display = box.style.display === 'none' ? 'flex' : 'none';
    }

    function handleEnter(e) {
        if (e.key === 'Enter') sendMessage();
    }

    async function sendMessage() {
        const inputField = document.getElementById('user-input');
        const messageBox = document.getElementById('chat-messages');
        const question = inputField.value.trim();

        if (!question) return;

        // 1. Add User Message
        messageBox.innerHTML += `<div style="text-align: right; margin: 5px 0;"><span style="background: #007bff; color: white; padding: 6px 10px; border-radius: 10px; display: inline-block;">${question}</span></div>`;
        inputField.value = '';
        messageBox.scrollTop = messageBox.scrollHeight;

        // 2. Add "Thinking..." indicator
        const loadingId = 'loading-' + Date.now();
        messageBox.innerHTML += `<div id="${loadingId}" style="margin: 5px 0;"><span style="color: #666; font-style: italic;">Typing...</span></div>`;

        try {
            // REPLACE THIS URL with your actual Server URL after deployment
            const response = await fetch('http://localhost:8000/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: question })
            });
            const data = await response.json();
            
            // 3. Add Bot Response
            document.getElementById(loadingId).remove();
            messageBox.innerHTML += `<div style="margin: 5px 0;"><span style="background: #e9ecef; color: black; padding: 6px 10px; border-radius: 10px; display: inline-block;">${data.answer}</span></div>`;
        } catch (error) {
            document.getElementById(loadingId).remove();
            messageBox.innerHTML += `<div style="color: red; font-size: 12px;">Error connecting to server.</div>`;
        }
        messageBox.scrollTop = messageBox.scrollHeight;
    }
</script>
5. Phase 4: Deployment & Maintenance
Since Moodle is usually on PHP hosting, you cannot run this Python bot on the same server unless it's a VPS/Dedicated server.

Recommended Deployment:

Deploy the Python Backend: Use Railway.app or Render.com (Free tiers available).

Upload your Python files and requirements.txt.

Set the Start Command to: uvicorn server:app --host 0.0.0.0 --port 8000

Get your public URL (e.g., https://lilit-bot.up.railway.app).

Update Frontend:

Replace http://localhost:8000/chat in the HTML snippet above with your new Railway/Render URL.

Maintenance:

Whenever you add a new course to LILIT, save the course outline as a PDF in the docs folder.

Run python indexer.py locally to update the database.

Re-upload the chroma_db folder to your server.
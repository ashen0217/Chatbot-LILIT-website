import os
# 1. SET THIS BEFORE ANYTHING ELSE IS IMPORTED!
os.environ["USER_AGENT"] = "LILIT_Chatbot/1.0"

import glob
import time
import shutil
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv

# Langchain imports
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader, WebBaseLoader
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv() 
 
BASE_URL = "https://lms.lilit.lk/" 
 
def get_all_website_links(url): 
    urls = set() 
    domain_name = urlparse(url).netloc 
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.content, "html.parser")
        for a_tag in soup.findAll("a"):
            href = a_tag.attrs.get("href")
            if href and "login" not in href:
                href = urljoin(url, href)
                parsed_href = urlparse(href)
                href = parsed_href.scheme + "://" + parsed_href.netloc + parsed_href.path
                if domain_name in href:
                    urls.add(href)
    except Exception as e:
        print(f"   ⚠️ Crawl error: {e}")
    return list(urls)

def build_knowledge_base():
    # Updated print statement
    print("--- 🚀 Starting High-Efficiency FAISS Indexing (OpenAI) ---")
    
    if os.path.exists("./faiss_db"):
        shutil.rmtree("./faiss_db")
        print("   ... Old database cleared.")

    all_docs = []

    # --- 1. LOCAL FILES ---
    print("   ... 📂 Loading Local Documents...")
    for file_path in glob.glob("docs/**/*.txt", recursive=True):
        try:
            txt_loader = TextLoader(file_path, encoding='utf-8')
            all_docs.extend(txt_loader.load())
        except Exception as e:
            print(f"       ⚠️ Could not load {file_path}: {e}")

    for file_path in glob.glob("docs/**/*.pdf", recursive=True):
        try:
            pdf_loader = PyPDFLoader(file_path)
            all_docs.extend(pdf_loader.load())
        except Exception as e:
            print(f"       ⚠️ Could not load {file_path}: {e}")

    # --- 2. WEB SCRAPING ---
    print("   ... 🕸️ Crawling website...")
    found_urls = get_all_website_links(BASE_URL)
    
    critical_urls = {
        "https://lms.lilit.lk/course-details/2",
        "https://lms.lilit.lk/course-details/3",
        "https://lms.lilit.lk/course-details/4",
        "https://lms.lilit.lk/course-details/5",
        "https://lms.lilit.lk/course-details/7",
        "https://lms.lilit.lk/news",
        "https://lms.lilit.lk/all-courses",
        "https://lms.lilit.lk/about"
    }
    
    all_targets = list(set(found_urls).union(critical_urls))
    target_urls = all_targets[:25] 
    print(f"   ... Indexing {len(target_urls)} web pages.")
    
    try:
        # FORCING the User-Agent directly into the WebBaseLoader
        web_loader = WebBaseLoader(
            target_urls, 
            requests_kwargs={"headers": {"User-Agent": "LILIT_Chatbot/1.0"}}
        )
        web_loader.requests_per_second = 1
        all_docs.extend(web_loader.load())
    except Exception as e:
        print(f"   ⚠️ Web scraping warning: {e}")

    # --- 3. SAFETY CHECK ---
    if len(all_docs) == 0:
        print("❌ CRITICAL ERROR: No documents or web pages were loaded. Cannot build database.")
        return

    # --- 4. CHUNKING ---
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    all_splits = text_splitter.split_documents(all_docs)
    print(f"   ... Total chunks generated: {len(all_splits)}")

    if len(all_splits) == 0:
        print("❌ CRITICAL ERROR: Documents were loaded, but no text could be extracted.")
        return

    # --- 5. FAISS UPLOAD ---
    # Updated print statement to reflect OpenAI
    print("   ... 💾 Saving to FAISS Database (using OpenAI)...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    batch_size = 20
    vectorstore = None
    
    for i in range(0, len(all_splits), batch_size):
        batch = all_splits[i : i + batch_size]
        try:
            if vectorstore is None:
                vectorstore = FAISS.from_documents(batch, embeddings)
            else:
                vectorstore.add_documents(batch)
            print(f"       ✅ Indexed {i+len(batch)}/{len(all_splits)} chunks")
        except Exception as e:
            print(f"       ⚠️ Quota hit. Waiting 10s... (Error: {e})")
            time.sleep(10)
            try:
                if vectorstore is None:
                    vectorstore = FAISS.from_documents(batch, embeddings)
                else:
                    vectorstore.add_documents(batch)
                print(f"       ✅ Recovered and indexed {i+len(batch)}/{len(all_splits)} chunks")
            except Exception as e2:
                print(f"       ❌ Failed batch after waiting. Skipping. (Error: {e2})")

    # --- 6. SAVE DB ---
    if vectorstore is not None:
        vectorstore.save_local("./faiss_db")
        print("✅ SUCCESS: FAISS Indexing Complete! The faiss_db folder has been created.")
    else:
        print("❌ ERROR: Vectorstore was never created. Check API keys and quotas.")

if __name__ == "__main__":
    build_knowledge_base()
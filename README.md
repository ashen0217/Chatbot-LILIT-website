# LILIT Chatbot Project

A smart AI-powered chatbot for the **Lanka Institute of Language and Information Technology (LILIT)**. This chatbot helps users navigate the LILIT LMS, providing information about courses, contact details, and general inquiries using a Retrieval-Augmented Generation (RAG) approach.

## 🚀 Features

- **AI-Powered Responses**: Uses Google's **Gemini Pro** model for intelligent, context-aware answers.
- **RAG Architecture**: Retrieves relevant information from a local vector database created from LILIT's documents and website.
- **Modern UI**: A responsive, premium chatbot interface with typing animations and brand-specific styling.
- **FastAPI Backend**: A robust Python backend serving the AI logic.

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.9+**: [Download Python](https://www.python.org/downloads/)
- **Git**: [Download Git](https://git-scm.com/downloads)

## 🔑 AI API Key Configuration

To use this chatbot, you need a Google Gemini API Key.

1.  Go to **[Google AI Studio](https://aistudio.google.com/)**.
2.  Sign in with your Google account.
3.  Click on **"Get API key"**.
4.  Copy the generated key string.

## 📦 Installation & Setup

Follow these steps to set up the project locally.

### 1. Clone the Repository

```bash
git clone https://github.com/WebcommsGlobal/lilit_chatbot.git
cd lilit_chatbot
```

### 2. Create a Virtual Environment

It is recommended to use a virtual environment to manage dependencies.

**Windows:**

```bash
python -m venv venv
.\venv\Scripts\activate
```

**Mac/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

Install the required Python libraries listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

1.  Create a file named `.env` in the root directory.
2.  Add your Google API key to it:

```env
GOOGLE_API_KEY=your_actual_api_key_here
```

## 🏗️ Building the Knowledge Base

Before running the server, you need to index the data. The `indexer.py` script will:

- Read local documents from the `docs/` folder (PDFs, TXTs).
- Crawl the `https://lms.lilit.lk/` website for latest content.
- Create a vector database in the `chroma_db/` folder.

Run the indexer:

```bash
python indexer.py
```

_Note: This process may take a few minutes depending on the data size._

## 🚀 Running the Chatbot

### 1. Start the Backend Server

Start the FastAPI server using `uvicorn`:

```bash
uvicorn server:app --reload
```

The server will start at `http://127.0.0.1:8000`.

### 2. Launch the Frontend

Simply open the `index.html` file in your preferred web browser.

- You can double-click `index.html` in your file explorer.
- Or verify it is connected to the backend by typing "Hello" in the chat.

## 📂 Project Structure

- `server.py`: Main backend application handling chat requests.
- `indexer.py`: Script to build and update the vector database.
- `index.html`: The frontend user interface.
- `requirements.txt`: List of Python dependencies.
- `docs/`: Folder to place local documents for indexing.
- `chroma_db/`: Generated vector database storage (do not edit manually).

## 📚 Libraries Used

- **FastAPI**: High-performance web framework for APIs.
- **LangChain**: Framework for developing applications powered by LLMs.
- **ChromaDB**: AI-native open-source embedding database.
- **Google Gemini**: State-of-the-art AI model by Google.
- **BeautifulSoup**: Library for pulling data out of HTML and XML files.

---

**Developed for LILIT LMS**

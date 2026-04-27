# Architecture & Flow Diagrams

## Request Flow: Course Query (Fixed) ✅

```
User Input: "What are the courses available?"
        ↓
[Greeting Check]
  - Not a greeting → Continue
        ↓
[Off-Topic Filter]
  - Check if LILIT-related
  - "courses" is in keywords
  - Passes filter → Continue
        ↓
[Course Count Query?]
  - Pattern: "how many courses"
  - Not matched → Continue
        ↓
[Objectives Query?]
  - Pattern: "objective|aims|goals"
  - Not matched → Continue
        ↓
[Vision/Mission Query?]
  - Pattern: "vision|mission"
  - Not matched → Continue
        ↓
[GENERAL COURSE QUERY] ← FIX APPLIED HERE
  - Pattern: "courses?|course details|..." ← NEW: Added "courses?"
  - MATCHED ✅ → Fetch course data
        ↓
[Get Hardcoded Course Data]
  - 5 courses with details
  - Duration, fee, overview
        ↓
[LLM Formatting]
  - Format response in user language
  - Structure course information
        ↓
[Stream Response to User]
  - Send each token
  - End with [DONE]
        ↓
User sees: All 5 courses with details ✅
```

---

## Server Initialization (Fixed) ✅

```
Server Startup
     ↓
[Load Environment Variables]
     ↓
[Initialize OpenAI Embeddings]
     ↓
[Load Pinecone Database] ← ERROR HANDLING ADDED HERE
     ↓
  ┌─────────────────────────────────────────┐
  │ TRY to load from existing index         │
  └─────────────────────────────────────────┘
     ↓
  ┌──────────┬──────────┐
  │          │          │
SUCCESS   FAILURE    TIMEOUT
  │          │          │
  ↓          ↓          ↓
Loaded   Exception   Exception
  │          │          │
  ↓          ↓          ↓
  ┌──────────┴──────────┴──────────┐
  │ vectorstore = None             │
  │ Log warning message            │
  │ Continue with fallback mode    │
  └────────────────────────────────┘
     ↓
[Setup QA Chain] ← CONDITIONAL SETUP HERE
     ↓
  IF vectorstore:
    qa_chain = create_chain()    ✅ Full power
  ELSE:
    qa_chain = None              ⚠️ Fallback mode
     ↓
[Setup FastAPI routes]
     ↓
[Ready to serve] ← Server ALWAYS reaches this point ✅
     ↓
[Uvicorn running on :8000]
```

---

## Query Processing: Pinecone Availability Handling

```
User Submits Query
     ↓
[Pass domain guard check]
     ↓
[Check special handlers]
  - Greetings?
  - Course count?
  - Objectives?
  - Vision/Mission?
  - etc.
     ↓
[Generic database query fallback]
     ↓
    ┌─────────────────────────┐
    │ IF qa_chain is available│
    └─────────────────────────┘
    ↓              ↓
 YES              NO
  │               │
  ↓               ↓
[Use knowledge   [Send helpful
 base]           error message]
  │               │
  ↓               ↓
[Return AI      [Return fallback]
 enhanced
 response]
  │               │
  ├───────┬───────┤
  ↓       ↓
Stream response to user ✅
```

---

## Graceful Degradation Matrix

```
                  Scenario 1         Scenario 2         Scenario 3
                 (Ideal)            (Degraded)         (Failed)
              ─────────────────────────────────────────────────────
Pinecone         ✅ Connected      ⚠️ Unreachable      ❌ Down/Error
Status           (Ready)           (Timeout)          (API Error)

vectorstore      ✅ Loaded          ✅ None            ✅ None
State            (Active)           (Fallback)         (Fallback)

qa_chain         ✅ Initialized     ✅ None            ✅ None
Status           (Active)           (Fallback)         (Fallback)

Server           ✅ Starts          ✅ Starts          ✅ Starts
                                    (+ warning)        (+ warning)

Course           ✅ Full power      ✅ Hardcoded       ✅ Hardcoded
Data             (DB + AI)          (5 courses)        (5 courses)

Vision/          ✅ Full power      ✅ Hardcoded       ✅ Hardcoded
Mission          (DB + AI)          (canonical)        (canonical)

Contact          ✅ Full power      ✅ Hardcoded       ✅ Hardcoded
Info             (DB + AI)          (canonical)        (canonical)

General          ✅ Full power      ❌ Can't answer     ❌ Can't answer
Queries          (DB + AI)          (fallback msg)      (fallback msg)

User             ✅ Great           ✅ Partial service ✅ Service degrades
Experience       (Full service)     (Better than        gracefully
                                     crash)             (No crash!)
```

---

## Code Fix Locations

```
server.py Structure:

Line 1-49:    Imports & setup

Line 51-61:   *** FIX #1: Pinecone Error Handling ***
              try:
                  vectorstore = ...
              except:
                  vectorstore = None

Line 63-65:   LLM Setup

Line 66-113:  Prompt template

Line 115-131: *** FIX #2: Conditional Chain Setup ***
              if vectorstore:
                  qa_chain = ...
              else:
                  qa_chain = None

Line 127-430: Request models, cache, helper functions

Line 434:     @app.post("/chat") endpoint

Line 439-705: Chat generation logic

Line 668:     *** FIX #3: Course Query Regex ***
              r"\b(courses?|course..)\b"
                    ^^^^^^^^
                    NEW: Match singular/plural

Line 697-704: *** FIX #4: Safe Query Execution ***
              if qa_chain:
                  async for chunk in qa_chain...
              else:
                  yield fallback_message

Line 706+:    Error handling & stream end
```

---

## Before vs After: Visual Comparison

### Problem 1: Course Query

```
BEFORE:
User: "What are the courses available in lilit?"
        ↓
    [Regex Check]
    Pattern: r"\b(course details|course fees|...)\b"
    "courses" NOT in list → NO MATCH
        ↓
    [Question 6: Check domain]
    "courses" IS in keywords → LILIT-related
        ↓
    [Generic DB Query]
    Retrieves snippets → AI answers
    Result: UNPREDICTABLE
        ↓
User sees: ❌ "Not in database" or wrong answer

---

AFTER:
User: "What are the courses available in lilit?"
        ↓
    [Regex Check]
    Pattern: r"\b(courses?|course details|...)\b"
    "courses" MATCHES "courses?" ✅ MATCH
        ↓
    [Get Hardcoded Course Data]
    5 courses with details
        ↓
    [Format & Stream]
    Structured response
        ↓
User sees: ✅ All 5 courses with full details
```

### Problem 2: Pinecone Failure

```
BEFORE:
Server Startup
     ↓
[Load Pinecone]
     ↓
vectorstore = PineconeVectorStore.from_existing_index(...)
     ↓
❌ EXCEPTION (No API key, wrong region, etc.)
     ↓
💥 CRASH - Program exits
     ↓
❌ Server not running
❌ User can't access chatbot
❌ No error message
❌ No logs showing why

---

AFTER:
Server Startup
     ↓
[Load Pinecone with error handling]
     ↓
TRY:
  vectorstore = PineconeVectorStore.from_existing_index(...)
EXCEPT:
  print("⚠ Warning: Failed to load...")
  vectorstore = None
     ↓
[Setup conditional chain]
IF vectorstore:
  qa_chain = chain()
ELSE:
  qa_chain = None
     ↓
✅ Continue startup
✅ All other routes work
✅ Server running
✅ Clear warning in logs
✅ Hardcoded data available
     ↓
✅ Server running successfully
✅ User can access chatbot
✅ Partial service available
✅ Clear error messages
```

---

## Decision Tree: Query Processing

```
        START: User submits question
             ↓
        ┌─────────────────┐
        │ Greeting Test?  │
        └────┬────────┬───┘
            YES       NO
             │        │
             ↓        ↓
          [Return] [Continue]
          greeting
             ↓
        ┌──────────────────────┐
        │ LILIT-Related Query? │
        └────┬──────────────┬──┘
            YES              NO
             │               │
             ↓               ↓
          [Continue]    [Return OFF-TOPIC]
             │
    ┌────────┼────────┬─────────────────┬──────────────────┐
    │        │        │                 │                  │
    ↓        ↓        ↓                 ↓                  ↓
[Course] [Objective][Vision/] [News/] [GENERAL COURSE] [Generic DB]
[Count]  [s/About]  [Mission] [Events] [QUERY] ← FIX HERE
    │        │        │                 │                  │
    ↓        ↓        ↓                 ↓                  ↓
[Fetch]  [Return]  [Return]      [Scrape] [Fetch        [Check
[Count]  [Hardcoded][Hardcoded]    [Live]  Hardcoded] ← qa_chain]
    │        │        │                 │                  │
    ↓        ↓        ↓                 ↓                  │
                                                    ┌──────┴──────┐
                                                    │             │
                                                 YES              NO
                                                    │             │
                                                    ↓             ↓
                              [Use qa_chain]  [Return Error]
                                    │              Msg
                                    │
    ┌───────────────────────────────┼───────┐
    │                               │       │
    ↓                               ↓       ↓
[ALL PATHS CONVERGE: Stream Response & [DONE]]
    │
    ↓
User receives response ✅
```

---

## Environment Setup Diagram

```
Render Environment

┌─────────────────────────────────────────┐
│         Render Dashboard                │
│  Settings → Environment → Add Variables │
└────────────┬────────────────────────────┘
             │
    ┌────────┼────────┐
    │        │        │
    ↓        ↓        ↓
OPENAI_   PINECONE_  PINECONE_
API_KEY   API_KEY    INDEX_NAME
    │        │        │
    └────────┼────────┘
             ↓
   ┌────────────────┐
   │ server.py      │
   │ Reads env vars │
   └────┬───────────┘
        │
        ↓
   ┌────────────────┐
   │ Initialize:    │
   │ - Embeddings   │
   │ - LLM          │
   │ - Vectorstore  │ ← Error handled here
   │ - qa_chain     │ ← Conditional setup here
   └────┬───────────┘
        │
        ↓
   ✅ Server Ready
```

---

## Testing Coverage

```
Test Suite: test_fixes.py

┌─────────────────────────────────────────┐
│    Test 1: Course Query Regex           │
├─────────────────────────────────────────┤
│ ✅ "What are the courses available?"   │
│ ✅ "Tell me about the courses"         │
│ ✅ "all courses"                       │
│ ✅ "courses offered"                   │
│ ✅ "what courses"                      │
│ ✅ "list courses"                      │
│ ✅ "course details"                    │
│ ✅ "How many courses?"                 │
│ ✅ Off-topic rejected                  │
│ RESULT: 9/9 PASSED ✅                  │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Test 2: Pinecone Error Handling        │
├─────────────────────────────────────────┤
│ ✅ Server imports successfully         │
│ ✅ Handles missing index gracefully    │
│ ✅ Clear warning message logged        │
│ RESULT: ALL PASSED ✅                  │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Test 3: QA Chain Availability          │
├─────────────────────────────────────────┤
│ ✅ Chain=None when vectorstore=None    │
│ ✅ Chain available when connected      │
│ RESULT: ALL PASSED ✅                  │
└─────────────────────────────────────────┘

OVERALL: 3/3 Test Categories PASSED ✅
```

---

## Deployment Timeline

```
Preparation Phase
  │
  ├─ Code Review      → COMPLETE ✅
  ├─ Testing          → COMPLETE ✅
  ├─ Documentation    → COMPLETE ✅
  └─ Quality Check    → COMPLETE ✅

Deployment Phase
  │
  ├─ Push to GitHub   → READY
  ├─ Render Deploy    → READY
  ├─ Set Env Vars     → REQUIRED
  └─ Verify           → REQUIRED

Verification Phase
  │
  ├─ Server Starts    → Expected ✅
  ├─ Course Query     → Expected ✅
  ├─ Log Check        → Required
  └─ Load Test        → Recommended

Post-Deployment
  │
  ├─ Monitor Logs     → Weekly
  ├─ Track Errors     → Daily
  └─ Performance      → As needed
```

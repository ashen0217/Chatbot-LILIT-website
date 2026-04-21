# Quick Test Guide - Vision & Mission

## Start the Server

```bash
cd D:\Games\Chatbot-LILIT-website
python server.py
```

## Test Cases to Verify 100% Accuracy

### Test 1: Sinhala Vision ✅

**Ask:** `දැක්ම?`

**Expected Response:**

```
රාජ්‍ය නිලධාරීන්ගේ එදිනෙදා කාර්යාලීය කටයුතු වඩාත් කාර්යක්ෂම කරගැනීම සහ මහජනතාව වෙත වඩාත් කාර්යක්ෂම, කඩිනම් සහ ගුණාත්මක සේවාවක් ලබා දීම උදෙසා කෘත්‍රිම බුද්ධිය ප්‍රායෝගිකව භාවිතා කරන ආකාරය පිළිබඳව පුහුණුවක් ලබා දීමයි.
```

### Test 2: English Vision ✅

**Ask:** `vision?`

**Expected Response:**

```
Empowering the Future: Introducing Robotics Education for Children at LILIT
```

### Test 3: English Mission ✅

**Ask:** `mission?`

**Expected Response:**

```
To revolutionize education through innovative technology solutions that empower institutions, educators, and students to achieve their full potential.
```

### Test 4: Variations ✅

These should also work:

- `What is the vision?`
- `Tell me about LILIT vision`
- `vision of lilit`
- `What is your mission?`
- `LILIT mission statement`

## How to Verify

1. Open browser: http://127.0.0.1:8000
2. Ask each question above
3. Compare response with expected text
4. Should be **EXACTLY** the same - word for word!

## Success Criteria

- ✅ Response matches expected text 100%
- ✅ No extra words or explanations
- ✅ Correct language (Sinhala for දැක්ම, English for vision/mission)
- ✅ Instant response (uses hardcoded data)

## If Something is Wrong

Check that you're running from the correct directory:

```bash
cd D:\Games\Chatbot-LILIT-website
pwd  # Should show: D:\Games\Chatbot-LILIT-website
```

Not from: `D:\Games\lilit_chatbot_openai-main\` ❌

# 🤖 AI Chatbot with Memory

### DecodeLabs Industrial Training Kit | Batch 2026 | Project 1

A full-stack conversational web application that remembers previous user messages during a live session using an in-memory history array and a sliding window algorithm.

---

## 📸 Preview

> Start the app, open `http://localhost:5000` in your browser and start chatting!

---

## 🎯 Project Goal

Build a conversational web app that remembers previous user messages during a live session by maintaining an active in-memory list array and appending every new user input and model response to the history payload to preserve context.

---

## ✅ Key Requirements Met

| Requirement | Implementation |
|---|---|
| Connect to a frontier LLM via official SDK | Groq SDK with `llama-3.3-70b-versatile` model |
| Maintain an active in-memory history array | `conversation_history = []` in `app.py` |
| Append every user input to history | `history.append({"role": "user", "content": ...})` |
| Append every model response to history | `history.append({"role": "assistant", "content": ...})` |
| Structural Validation Gate | Empty input blocked before reaching API |
| Sliding Window (FIFO pruning) | Oldest message pairs dropped when history exceeds 20 messages |

---

## 🧠 How Memory Works

LLMs are stateless — they forget everything between API calls. Memory is simulated by sending the **entire conversation history** as the `messages` parameter on every API request:

```
Turn 1 → API receives: [user: "hi"]
Turn 2 → API receives: [user: "hi", ai: "hello!", user: "my name is Asif"]
Turn 3 → API receives: [user: "hi", ai: "hello!", user: "my name is Asif", ai: "Nice to meet you!", user: "what is my name?"]
```

The model sees all prior context each time, so it responds coherently across the session.

---

## 🪟 Sliding Window Algorithm

When `conversation_history` exceeds 20 messages, the oldest message pair is automatically dropped (FIFO) to stay within the model's token limit:

```
Before: [msg0, msg1, msg2, msg3, msg4]   ← exceeds limit
After:  [msg2, msg3, msg4]               ← oldest pair dropped
```

---

## 🗂️ Project Structure

```
ai-chatbot-with-memory/
├── app.py              ← Flask backend (memory logic, API calls, sliding window)
├── static/
│   └── index.html      ← Frontend chat UI (HTML + CSS + JS)
├── requirements.txt    ← Python dependencies
├── .env.example        ← Template for environment variables
├── .gitignore          ← Keeps API keys out of GitHub
└── README.md           ← This file
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, Vanilla JavaScript |
| Backend | Python, Flask |
| AI Model | Llama 3.3 70B (via Groq API) |
| Memory | In-memory Python list (session-scoped) |

---

## 🚀 Setup & Run

### 1. Clone the repository
```bash
git clone https://github.com/your-username/ai-chatbot-with-memory.git
cd ai-chatbot-with-memory
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up your API key

Get a free Groq API key at **https://console.groq.com**

Copy the example env file and add your key:
```bash
cp .env.example .env
```

Open `.env` and replace the placeholder:
```
GROQ_API_KEY=your-actual-groq-api-key-here
```

### 4. Run the app
```bash
python app.py
```

### 5. Open in browser
```
http://localhost:5000
```

---

## 🧪 Testing Memory (The Memory Exam)

Run this exact sequence to verify memory is working:

| Step | You type | Expected |
|---|---|---|
| 1 | `My name is Asif` | AI acknowledges your name |
| 2 | `Write a poem about technology` | AI writes a poem (context distraction) |
| 3 | `What is my name?` | AI correctly replies **"Asif"** ✅ |

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serves the chat UI |
| `/chat` | POST | Sends a message, returns AI reply |
| `/history` | GET | Returns the raw history array (debug) |
| `/clear` | POST | Resets the conversation history |

---

## 🔑 Key Concepts Demonstrated

- **Stateless vs Stateful APIs** — Understanding why history must be sent on every request
- **Session State Management** — Maintaining context across multiple turns
- **FIFO Sliding Window** — Preventing token budget exhaustion on long conversations
- **Structural Validation Gate** — Blocking empty inputs before they reach the API
- **Full-Stack AI Integration** — Connecting a frontend UI to a Python AI backend

---

## 🌐 Key Skills

`API Integration` · `Session State Management` · `Chat History Mechanics` · `Flask` · `Groq SDK` · `Python`

---

*Built as part of the DecodeLabs Generative AI Industrial Training Program — Batch 2026*
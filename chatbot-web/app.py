"""
DecodeLabs Internship - Project 1
Custom AI Chatbot with Memory - Web App Version
Backend: Flask + Groq API
"""

import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

# ── Configuration ──────────────────────────────────────────────────────────────
API_KEY      = os.getenv("GROQ_API_KEY", "")
MODEL        = "llama-3.3-70b-versatile"
MAX_TOKENS   = 1024
MAX_HISTORY  = 20
SYSTEM_PROMPT = (
    "You are a helpful AI assistant with memory. "
    "You remember everything the user tells you during this session "
    "and refer back to it accurately when relevant. "
    "Be friendly, concise, and natural in conversation."
)

# ── Flask app setup ────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static")
CORS(app)

# ── Groq client ────────────────────────────────────────────────────────────────
client = Groq(api_key=API_KEY)

# ── In-memory conversation history (lives as long as server runs) ──────────────
conversation_history = []

# ── Sliding Window (FIFO pruning) ─────────────────────────────────────────────
def apply_sliding_window(history, max_size):
    if len(history) > max_size:
        excess = len(history) - max_size
        excess = excess + (excess % 2)
        history = history[excess:]
    return history

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/chat", methods=["POST"])
def chat():
    global conversation_history

    data       = request.get_json()
    user_input = data.get("message", "").strip()

    # Structural Validation Gate
    if not user_input:
        return jsonify({"error": "Empty message blocked."}), 400

    # Append user message
    conversation_history.append({"role": "user", "content": user_input})

    # Apply sliding window
    conversation_history = apply_sliding_window(conversation_history, MAX_HISTORY)

    # Call Groq API with full history
    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history
        )
        assistant_reply = response.choices[0].message.content
    except Exception as e:
        conversation_history.pop()
        return jsonify({"error": str(e)}), 500

    # Append assistant response
    conversation_history.append({"role": "assistant", "content": assistant_reply})

    return jsonify({
        "reply":   assistant_reply,
        "history_count": len(conversation_history)
    })

@app.route("/history", methods=["GET"])
def get_history():
    return jsonify({"history": conversation_history})

@app.route("/clear", methods=["POST"])
def clear_history():
    global conversation_history
    conversation_history = []
    return jsonify({"message": "History cleared."})

# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  DecodeLabs Project 1 — Chatbot Web App")
    print("  Running at: http://localhost:5000")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)

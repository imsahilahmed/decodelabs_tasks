import os

from flask import Flask, jsonify, request, send_from_directory, render_template

from generator import OUTPUT_DIR, PipelineError, run_pipeline

app = Flask(__name__)


@app.route("/")
def index():
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    has_stability = bool(os.environ.get("STABILITY_API_KEY"))
    return render_template("index.html", has_openai=has_openai, has_stability=has_stability)


@app.route("/api/generate", methods=["POST"])
def generate():
    body = request.get_json(force=True) or {}
    prompt = (body.get("prompt") or "").strip()
    aspect_ratio = body.get("aspect_ratio", "1:1")
    style = body.get("style", "none")
    provider = body.get("provider", "mock")

    if not prompt:
        return jsonify({"error": "Prompt is required.", "stage": "payload"}), 400

    try:
        result = run_pipeline(prompt, aspect_ratio, style, provider)
    except PipelineError as e:
        return jsonify({"error": e.message, "stage": e.stage}), 422
    except Exception as e:  # pragma: no cover - safety net for the demo
        return jsonify({"error": str(e), "stage": "unknown"}), 500

    result["image_url"] = f"/outputs/{result['filename']}"
    return jsonify(result)


@app.route("/outputs/<path:filename>")
def outputs(filename):
    return send_from_directory(OUTPUT_DIR, filename)


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # use_reloader=False: the reloader's file-watcher otherwise restarts the
    # server every time a generated PNG lands in outputs/, killing in-flight
    # requests.
    app.run(host="0.0.0.0", port=5050, debug=True, use_reloader=False)

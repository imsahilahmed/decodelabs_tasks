const btn = document.getElementById("generateBtn");
const canvas = document.getElementById("canvas");
const meta = document.getElementById("meta");
const settingsBtn = document.getElementById("settingsBtn");
const settingsPanel = document.getElementById("settingsPanel");

settingsBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  settingsPanel.classList.toggle("open");
});
document.addEventListener("click", (e) => {
  if (!settingsPanel.contains(e.target) && e.target !== settingsBtn) {
    settingsPanel.classList.remove("open");
  }
});

const stageEls = {};
document.querySelectorAll(".stage").forEach((el) => {
  stageEls[el.dataset.stage] = el;
});

function resetStages() {
  Object.values(stageEls).forEach((el) => {
    el.className = "stage";
    el.querySelector(".stage-detail").textContent = "Waiting…";
  });
}

function markStage(stage, status, detail) {
  const el = stageEls[stage];
  if (!el) return;
  el.className = `stage ${status}`;
  el.querySelector(".stage-detail").textContent = detail;
}

async function replayLog(log) {
  for (const entry of log) {
    markStage(entry.stage, entry.status, `${entry.status.toUpperCase()} · t=${entry.t}s · ${entry.detail}`);
    await new Promise((r) => setTimeout(r, 220));
  }
}

btn.addEventListener("click", async () => {
  const prompt = document.getElementById("prompt").value.trim();
  if (!prompt) {
    alert("Enter a text description first.");
    return;
  }

  const payload = {
    prompt,
    provider: document.getElementById("provider").value,
    aspect_ratio: document.getElementById("aspect").value,
    style: document.getElementById("style").value,
  };

  btn.disabled = true;
  btn.querySelector(".run-btn-label").textContent = "RUNNING…";
  resetStages();
  meta.textContent = "";
  canvas.innerHTML = '<div class="canvas-empty">Generating…</div>';

  // Mark the current-in-flight stage as "active" for a spinner feel before
  // the response lands (single request/response backend, so this is a
  // lightweight approximation, not a live stream).
  markStage("payload", "active", "In progress…");

  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      if (data.stage) markStage(data.stage, "error", data.error || "Failed");
      meta.innerHTML = `<span class="meta-error">ERROR [${data.stage || "unknown"}] ${data.error}</span>`;
      canvas.innerHTML = '<div class="canvas-empty">Generation failed — see pipeline log</div>';
      return;
    }

    await replayLog(data.log);

    canvas.innerHTML = `<img src="${data.image_url}?t=${Date.now()}" alt="${prompt}">`;
    const resLine =
      data.requested_width && (data.requested_width !== data.width || data.requested_height !== data.height)
        ? `resolution: ${data.width}x${data.height} (requested ${data.requested_width}x${data.requested_height})`
        : `resolution: ${data.width}x${data.height}`;
    meta.innerHTML = [
      resLine,
      `qa_score: ${data.qa_score}/10.0`,
      `file: ${data.filename}`,
    ].join("<br>");
  } catch (err) {
    meta.innerHTML = `<span class="meta-error">ERROR [network] ${err}</span>`;
  } finally {
    btn.disabled = false;
    btn.querySelector(".run-btn-label").textContent = "RUN PIPELINE";
  }
});

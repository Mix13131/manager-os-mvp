async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

function pretty(targetId, payload) {
  document.getElementById(targetId).textContent = JSON.stringify(payload, null, 2);
}

document.getElementById("captureButton").addEventListener("click", async () => {
  const text = document.getElementById("captureText").value.trim();
  if (!text) return;
  const data = await postJson("/api/capture", { text, source: "web" });
  pretty("captureResult", data);
  window.location.reload();
});

document.getElementById("resetButton").addEventListener("click", async () => {
  const payload = {
    impact_focus: document.getElementById("impactFocus").value.trim(),
    operational_risk: document.getElementById("operationalRisk").value.trim(),
    managerial_action: document.getElementById("managerialAction").value.trim(),
  };
  const data = await postJson("/api/rituals/daily-reset", payload);
  pretty("resetResult", data);
});

document.getElementById("weeklyButton").addEventListener("click", async () => {
  const data = await postJson("/api/weekly-review", {});
  pretty("weeklyResult", data);
});

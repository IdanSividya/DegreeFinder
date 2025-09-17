const API = "http://localhost:8000";

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error("Network error");
  return await res.json();
}

function inputRow(name, allowedUnits) {
  const container = document.createElement("div");
  container.className = "row";
  const label = document.createElement("label");
  label.textContent = name;
  const units = document.createElement("input");
  units.type = "number";
  units.min = Math.min(...allowedUnits);
  units.max = Math.max(...allowedUnits);
  units.step = 1;
  units.value = allowedUnits[allowedUnits.length - 1];

  const score = document.createElement("input");
  score.type = "number";
  score.min = 0;
  score.max = 100;
  score.step = 0.1;
  score.value = 90;

  container.appendChild(label);
  container.appendChild(units);
  container.appendChild(score);
  container.dataset.name = name;
  container.dataset.allowed = JSON.stringify(allowedUnits);
  return container;
}

function readSubjects(containerId) {
  const rows = document.getElementById(containerId).querySelectorAll(".row");
  const arr = [];
  rows.forEach(r => {
    const name = r.dataset.name;
    const allowed = JSON.parse(r.dataset.allowed);
    const inputs = r.querySelectorAll("input");
    const u = parseInt(inputs[0].value, 10);
    const s = parseFloat(inputs[1].value);
    if (allowed.includes(u)) {
      arr.push({ name: name, units: u, score: s });
    }
  });
  return arr;
}

async function main() {
  const subjects = await fetchJSON(`${API}/subjects?institution=technion`);
  const mandatoryDiv = document.getElementById("mandatory");
  const electiveChips = document.getElementById("elective-chips");
  const electivesDiv = document.getElementById("electives");

  subjects.mandatory.forEach(m => {
    mandatoryDiv.appendChild(inputRow(m.name, m.allowed_units));
  });

  subjects.electives.forEach(e => {
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.textContent = e.name;
    chip.onclick = () => {
      if (chip.classList.contains("selected")) {
        chip.classList.remove("selected");
        // remove the row
        const rows = electivesDiv.querySelectorAll(".row");
        rows.forEach(r => {
          if (r.dataset.name === e.name) {
            electivesDiv.removeChild(r);
          }
        });
      } else {
        chip.classList.add("selected");
        electivesDiv.appendChild(inputRow(e.name, e.allowed_units));
      }
    };
    electiveChips.appendChild(chip);
  });

  document.getElementById("compute").onclick = async () => {
    const psy = parseInt(document.getElementById("psy").value, 10);
    const payload = {
      institution: "technion",
      psychometric_total: psy,
      subjects: [
        ...readSubjects("mandatory"),
        ...readSubjects("electives")
      ]
    };
    const res = await fetch(`${API}/compute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    renderResults(data);
  };
}

function renderResults(data) {
  const root = document.getElementById("results");
  root.innerHTML = "";
  data.forEach(p => {
    const card = document.createElement("div");
    card.className = "card";
    const status = document.createElement("div");
    status.className = p.passed ? "results-pass" : "results-fail";
    status.textContent = p.passed ? "עבר ✓" : "לא עבר ✗";

    const title = document.createElement("h3");
    title.textContent = `${p.program_name} (${p.program_id})`;

    const metrics = document.createElement("div");
    metrics.innerHTML = `
      <div class="grid small">
        <div><b>D</b>: ${p.D?.toFixed ? p.D.toFixed(2) : p.D}</div>
        <div><b>P</b>: ${p.P}</div>
        <div><b>S</b>: ${p.S?.toFixed ? p.S.toFixed(2) : p.S}</div>
        <div><b>Threshold</b>: ${p.threshold ?? "-"}</div>
      </div>
    `;

    const expl = document.createElement("ul");
    p.explanations.forEach(x => {
      const li = document.createElement("li");
      li.textContent = x;
      expl.appendChild(li);
    });

    card.appendChild(title);
    card.appendChild(status);
    card.appendChild(metrics);
    card.appendChild(expl);
    root.appendChild(card);
  });
}

main().catch(err => console.error(err));

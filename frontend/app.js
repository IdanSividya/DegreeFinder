const API = "http://localhost:8000";

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Network error: ${res.status}`);
  return await res.json();
}

function clearChildren(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function unitsSelect(allowedUnits) {
  const sel = document.createElement("select");
  sel.className = "units";
  const opt0 = document.createElement("option");
  opt0.value = "";
  opt0.textContent = "בחר יח״ל";
  sel.appendChild(opt0);
  allowedUnits.forEach(u => {
    const opt = document.createElement("option");
    opt.value = String(u);
    opt.textContent = String(u);
    sel.appendChild(opt);
  });
  return sel;
}

function scoreInput() {
  const inp = document.createElement("input");
  inp.type = "number";
  inp.className = "score";
  inp.min = 0;
  inp.max = 100;
  inp.step = 0.1;
  inp.placeholder = "ציון";
  return inp;
}

function inputRow(internalName, displayName, allowedUnits, isMandatory) {
  const container = document.createElement("div");
  container.className = "row";
  const label = document.createElement("label");
  label.textContent = displayName;

  const unitsSel = unitsSelect(allowedUnits);
  const scoreInp = scoreInput();

  container.appendChild(label);
  container.appendChild(unitsSel);
  container.appendChild(scoreInp);

  container.dataset.name = internalName;
  container.dataset.display = displayName;
  container.dataset.allowed = JSON.stringify(allowedUnits);
  container.dataset.mandatory = isMandatory ? "1" : "0";
  return container;
}

function readSubjects(containerId, required) {
  const rows = document.getElementById(containerId).querySelectorAll(".row");
  const arr = [];
  const errors = [];
  rows.forEach(r => {
    const name = r.dataset.name;
    const display = r.dataset.display;
    const allowed = JSON.parse(r.dataset.allowed);
    const unitsSel = r.querySelector("select.units");
    const scoreInp = r.querySelector("input.score");
    const uRaw = unitsSel.value;
    const sRaw = scoreInp.value;

    if (required) {
      if (uRaw === "") {
        errors.push(`לא נבחר מספר יח״ל עבור "${display}".`);
      } else if (!allowed.includes(parseInt(uRaw, 10))) {
        errors.push(`מספר יח״ל עבור "${display}" אינו תקין.`);
      }
      if (sRaw === "") {
        errors.push(`לא הוזן ציון עבור "${display}".`);
      } else {
        const s = parseFloat(sRaw);
        if (isNaN(s) || s < 0 || s > 100) {
          errors.push(`ציון עבור "${display}" צריך להיות בין 0 ל־100.`);
        }
      }
    }

    if (!required) {
      if (uRaw !== "" && sRaw !== "") {
        const u = parseInt(uRaw, 10);
        const s = parseFloat(sRaw);
        if (allowed.includes(u) && !isNaN(s) && s >= 0 && s <= 100) {
          arr.push({ name: name, units: u, score: s });
        } else {
          errors.push(`"${display}" – ערכים לא תקינים.`);
        }
      }
    } else {
      if (uRaw !== "" && sRaw !== "") {
        arr.push({ name: name, units: parseInt(uRaw, 10), score: parseFloat(sRaw) });
      }
    }
  });
  return { subjects: arr, errors };
}

function showErrors(list) {
  const box = document.getElementById("errors");
  const ul = document.getElementById("errors-list");
  clearChildren(ul);
  if (list.length === 0) {
    box.style.display = "none";
    return;
  }
  list.forEach(msg => {
    const li = document.createElement("li");
    li.textContent = msg;
    ul.appendChild(li);
  });
  box.style.display = "block";
}

function hideErrors() {
  showErrors([]);
}

/* ---------- טעינת מקצועות ברירת מחדל (טכניון) ---------- */
async function loadDefaultSubjects() {
  const subjects = await fetchJSON(`${API}/subjects`); // ברירת מחדל: technion
  renderSubjects(subjects);
}

function renderSubjects(subjects) {
  const mandatoryDiv = document.getElementById("mandatory");
  const electiveChips = document.getElementById("elective-chips");
  const electivesDiv = document.getElementById("electives");
  clearChildren(mandatoryDiv);
  clearChildren(electiveChips);
  clearChildren(electivesDiv);

  subjects.mandatory.forEach(m => {
    const row = inputRow(m.name, m.display_name || m.name, m.allowed_units, true);
    mandatoryDiv.appendChild(row);
  });

  subjects.electives.forEach(e => {
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.textContent = e.display_name || e.name;
    chip.onclick = () => {
      if (chip.classList.contains("selected")) {
        chip.classList.remove("selected");
        const rows = electivesDiv.querySelectorAll(".row");
        rows.forEach(r => { if (r.dataset.name === e.name) electivesDiv.removeChild(r); });
      } else {
        chip.classList.add("selected");
        electivesDiv.appendChild(inputRow(e.name, e.display_name || e.name, e.allowed_units, false));
      }
    };
    electiveChips.appendChild(chip);
  });
}

/* ---------- מוסדות מרובים ---------- */
function hebrewInstitutionName(inst) {
  if (inst === "technion") return "הטכניון";
  return inst;
}

async function loadInstitutions() {
  const container = document.getElementById("institutions");
  clearChildren(container);
  const list = await fetchJSON(`${API}/institutions`);
  if (!Array.isArray(list) || list.length === 0) {
    container.textContent = "לא נמצאו מוסדות.";
    return;
  }
  list.forEach(inst => {
    const id = `inst_${inst}`;
    const row = document.createElement("div");
    row.className = "row";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.value = inst;
    cb.addEventListener("change", onInstitutionsChanged);

    const label = document.createElement("label");
    label.htmlFor = id;
    label.textContent = hebrewInstitutionName(inst);

    row.appendChild(cb);
    row.appendChild(label);
    container.appendChild(row);
  });
}

/* ---------- טעינת תארים (מסלולים) לפי מוסדות נבחרים ---------- */
async function onInstitutionsChanged() {
  hideErrors();
  document.getElementById("results").innerHTML = "";
  const selectedInsts = getSelectedInstitutions();
  const chipsRoot = document.getElementById("program-chips");
  const blockInfo = document.getElementById("programs-block");
  clearChildren(chipsRoot);

  if (selectedInsts.length === 0) {
    blockInfo.textContent = "בחר/י מוסד כדי לטעון את התארים שלו.";
    return;
  }

  blockInfo.textContent = "";
  for (const inst of selectedInsts) {
    const progs = await fetchJSON(`${API}/programs?institution=${encodeURIComponent(inst)}`);

    // כותרת לקבוצה
    const title = document.createElement("div");
    title.className = "group-title";
    title.textContent = `תארים – ${hebrewInstitutionName(inst)}`;
    chipsRoot.appendChild(title);

    // צ'יפים לבחירת תארים (אופציונלי)
    const chips = document.createElement("div");
    chips.className = "chips";
    progs.forEach(p => {
      const chip = document.createElement("div");
      chip.className = "chip";
      chip.textContent = `${p.name} (${p.id})`;
      chip.dataset.programId = p.id;
      chip.dataset.institution = p.institution;
      chip.onclick = () => {
        chip.classList.toggle("selected");
      };
      chips.appendChild(chip);
    });
    chipsRoot.appendChild(chips);
  }
}

function getSelectedInstitutions() {
  const container = document.getElementById("institutions");
  const cbs = container.querySelectorAll('input[type="checkbox"]');
  const arr = [];
  cbs.forEach(cb => { if (cb.checked) arr.push(cb.value); });
  return arr;
}

function getSelectedProgramIds() {
  const chipsRoot = document.getElementById("program-chips");
  const chips = chipsRoot.querySelectorAll(".chip.selected");
  const ids = [];
  chips.forEach(ch => {
    const id = ch.dataset.programId;
    if (id) ids.push(id);
  });
  return ids;
}

/* ---------- חישוב ---------- */
async function onCompute() {
  hideErrors();
  const errors = [];

  const insts = getSelectedInstitutions();
  if (insts.length === 0) {
    errors.push("יש לבחור לפחות מוסד אחד.");
  }

  const psyRaw = document.getElementById("psy").value;
  if (psyRaw === "") {
    errors.push("יש להזין ציון פסיכומטרי.");
  } else {
    const p = parseInt(psyRaw, 10);
    if (isNaN(p) || p < 200 || p > 800) errors.push("ציון פסיכומטרי חייב להיות בין 200 ל־800.");
  }

  const mandatoryRes = readSubjects("mandatory", true);
  const electiveRes = readSubjects("electives", false);
  errors.push(...mandatoryRes.errors, ...electiveRes.errors);

  if (errors.length > 0) {
    showErrors(errors);
    return;
  }

  const programIds = getSelectedProgramIds(); // יכול להיות ריק = כל התארים

  const payload = {
    institutions: insts,
    psychometric_total: parseInt(psyRaw, 10),
    subjects: [
      ...mandatoryRes.subjects,
      ...electiveRes.subjects
    ],
    program_ids: programIds
  };

  try {
    const res = await fetch(`${API}/compute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const txt = await res.text();
      showErrors([`שגיאת שרת (${res.status}): ${txt}`]);
      return;
    }
    const data = await res.json();
    renderResults(data);
  } catch (e) {
    showErrors([`שגיאה בתקשורת: ${e.message}`]);
  }
}

function renderResults(data) {
  const root = document.getElementById("results");
  root.innerHTML = "";
  if (!Array.isArray(data) || data.length === 0) {
    root.textContent = "לא נמצאו תוצאות עבור הבחירה.";
    return;
  }

  // ניתן למיין לפי מוסד/פאקולטה/סף אם רוצים; כרגע השארתי כפי שמוחזר
  data.forEach(p => {
    const card = document.createElement("div");
    card.className = "card";
    const status = document.createElement("div");
    status.className = p.passed ? "results-pass" : "results-fail";
    status.textContent = p.passed ? "עבר ✓" : "לא עבר ✗";

    const title = document.createElement("h3");
    const instHeb = hebrewInstitutionName(p.institution || "");
    title.textContent = `${instHeb} – ${p.program_name} (${p.program_id})`;

    const metrics = document.createElement("div");
    const d = p.D !== undefined && p.D !== null ? Number(p.D).toFixed(2) : "-";
    const s = p.S !== undefined && p.S !== null ? Number(p.S).toFixed(2) : "-";
    const t = p.threshold !== undefined && p.threshold !== null ? p.threshold : "-";
    metrics.className = "grid small";
    metrics.innerHTML = `
      <div><b>D</b>: ${d}</div>
      <div><b>P</b>: ${p.P ?? "-"}</div>
      <div><b>S</b>: ${s}</div>
      <div><b>סף</b>: ${t}</div>
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

/* ---------- main ---------- */
async function main() {
  // מזינים ציונים פעם אחת – טוענים מקצועות ברירת מחדל (טכניון) מיד
  await loadDefaultSubjects();
  // בוחרים מוסדות ותארים בנפרד
  await loadInstitutions();
  document.getElementById("compute").addEventListener("click", onCompute);
}

main().catch(err => showErrors([`שגיאה באתחול: ${err.message}`]));

const API = "http://localhost:8000";

/* ================= Utils ================= */
async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error("Network error: " + res.status);
  return await res.json();
}
function clearChildren(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function showErrors(list) {
  const box = document.getElementById("errors");
  const ul = document.getElementById("errors-list");
  clearChildren(ul);
  if (!list.length) { box.style.display = "none"; return; }
  list.forEach(msg => { const li = document.createElement("li"); li.textContent = msg; ul.appendChild(li); });
  box.style.display = "block";
}
function hideErrors(){ showErrors([]); }
function hebrewInstitutionName(inst) {
  const key = (inst || "").toLowerCase();
  if (key === "technion") return "הטכניון";
  if (key === "huji") return "האוניברסיטה העברית";
  if (key === "bgu") return "בן גוריון";
  return inst;
}
function safeNumberToFixed(value, digits) {
  if (value === undefined || value === null) return "-";
  const n = Number(value);
  if (isNaN(n)) return "-";
  return n.toFixed(digits);
}

/* ================= Subjects UI ================= */
function unitsSelect(allowedUnits) {
  const sel = document.createElement("select");
  sel.className = "units";
  const opt0 = document.createElement("option");
  opt0.value = ""; opt0.textContent = "בחר יח״ל";
  sel.appendChild(opt0);
  allowedUnits.forEach(u => {
    const opt = document.createElement("option");
    opt.value = String(u); opt.textContent = String(u);
    sel.appendChild(opt);
  });
  return sel;
}
function scoreInput() {
  const inp = document.createElement("input");
  inp.type = "number"; inp.className = "score"; inp.min = 0; inp.max = 100; inp.step = 0.1; inp.placeholder = "ציון";
  return inp;
}
function inputRow(internalName, displayName, allowedUnits, isMandatory) {
  const container = document.createElement("div");
  container.className = "row";
  const label = document.createElement("label"); label.textContent = displayName;
  const unitsSel = unitsSelect(allowedUnits);
  const scoreInp = scoreInput();
  container.appendChild(label); container.appendChild(unitsSel); container.appendChild(scoreInp);
  container.dataset.name = internalName;
  container.dataset.display = displayName;
  container.dataset.allowed = JSON.stringify(allowedUnits);
  container.dataset.mandatory = isMandatory ? "1" : "0";
  return container;
}
function readSubjects(containerId, required) {
  const rows = document.getElementById(containerId).querySelectorAll(".row");
  const arr = [], errors = [];
  rows.forEach(r => {
    const name = r.dataset.name;
    const display = r.dataset.display;
    const allowed = JSON.parse(r.dataset.allowed);
    const unitsSel = r.querySelector("select.units");
    const scoreInp = r.querySelector("input.score");
    const uRaw = unitsSel.value, sRaw = scoreInp.value;

    if (required) {
      if (uRaw === "") errors.push(`לא נבחר מספר יח״ל עבור "${display}".`);
      else if (!allowed.includes(parseInt(uRaw,10))) errors.push(`מספר יח״ל עבור "${display}" אינו תקין.`);
      if (sRaw === "") errors.push(`לא הוזן ציון עבור "${display}".`);
      else {
        const s = parseFloat(sRaw);
        if (isNaN(s) || s<0 || s>100) errors.push(`ציון עבור "${display}" צריך להיות בין 0 ל־100.`);
      }
    }

    if (!required) {
      if (uRaw !== "" && sRaw !== "") {
        const u = parseInt(uRaw,10), s = parseFloat(sRaw);
        if (allowed.includes(u) && !isNaN(s) && s>=0 && s<=100) arr.push({ name, units:u, score:s });
        else errors.push(`"${display}" – ערכים לא תקינים.`);
      }
    } else if (uRaw !== "" && sRaw !== "") {
      arr.push({ name, units: parseInt(uRaw,10), score: parseFloat(sRaw) });
    }
  });
  return { subjects: arr, errors };
}

/* ================= Subjects Load ================= */
async function loadDefaultSubjects() {
  const subjects = await fetchJSON(`${API}/subjects`);
  renderSubjects(subjects);
}
function renderSubjects(subjects) {
  const mandatoryDiv = document.getElementById("mandatory");
  const electiveChips = document.getElementById("elective-chips");
  const electivesDiv = document.getElementById("electives");
  clearChildren(mandatoryDiv); clearChildren(electiveChips); clearChildren(electivesDiv);

  subjects.mandatory.forEach(m => mandatoryDiv.appendChild(
    inputRow(m.name, m.display_name || m.name, m.allowed_units, true)
  ));

  subjects.electives.forEach(e => {
    const chip = document.createElement("div");
    chip.className = "chip"; chip.textContent = e.display_name || e.name;
    chip.onclick = () => {
      if (chip.classList.contains("selected")) {
        chip.classList.remove("selected");
        electivesDiv.querySelectorAll(".row").forEach(r => { if (r.dataset.name === e.name) electivesDiv.removeChild(r); });
      } else {
        chip.classList.add("selected");
        electivesDiv.appendChild(inputRow(e.name, e.display_name || e.name, e.allowed_units, false));
      }
    };
    electiveChips.appendChild(chip);
  });
}

/* ================= Institutions & Programs (by faculty with checkboxes) ================= */
const PROGRAM_CACHE = {};                   // { inst: Program[] }
const SELECTED_PROGRAM_IDS = new Set();     // user-selected programs
const FACULTY_SELECTIONS = {};              // { inst: Set<string> } – הצ׳קבוקסים שסומנו בכל מוסד

function getSelectedInstitutions() {
  const cbs = document.getElementById("institutions").querySelectorAll('input[type="checkbox"]');
  const arr = []; cbs.forEach(cb => { if (cb.checked) arr.push(cb.value); });
  return arr;
}

async function loadInstitutions() {
  const container = document.getElementById("institutions");
  clearChildren(container);
  const list = await fetchJSON(`${API}/institutions`);
  list.forEach(inst => {
    const id = `inst_${inst}`;
    const row = document.createElement("div"); row.className = "row";
    const cb = document.createElement("input"); cb.type = "checkbox"; cb.id = id; cb.value = inst;
    cb.addEventListener("change", onInstitutionsChanged);
    const label = document.createElement("label"); label.htmlFor = id; label.textContent = hebrewInstitutionName(inst);
    row.appendChild(cb); row.appendChild(label); container.appendChild(row);
  });
}

async function onInstitutionsChanged() {
  hideErrors();
  document.getElementById("results").innerHTML = "";

  const selectedInsts = getSelectedInstitutions();
  const chipsRoot = document.getElementById("program-chips");
  const blockInfo = document.getElementById("programs-block");
  clearChildren(chipsRoot);

  if (!selectedInsts.length) { blockInfo.textContent = "בחר/י מוסד כדי לטעון את התארים שלו."; return; }
  blockInfo.textContent = "";

  for (const inst of selectedInsts) {
    if (!PROGRAM_CACHE[inst]) PROGRAM_CACHE[inst] = await fetchJSON(`${API}/programs?institution=${encodeURIComponent(inst)}`);
    renderInstitutionFaculties(inst, PROGRAM_CACHE[inst], chipsRoot);
  }
}

function uniqueFaculties(programs) {
  const s = new Set();
  programs.forEach(p => { const f = (p.faculty || "").trim(); if (f) s.add(f); });
  return Array.from(s.values());
}

/* --- New: faculties rendered as checkboxes like institutions --- */
function renderInstitutionFaculties(inst, programs, parent) {
  const wrapper = document.createElement("div");
  wrapper.style.marginBottom = "16px";

  const title = document.createElement("div");
  title.className = "group-title";
  title.textContent = `תארים – ${hebrewInstitutionName(inst)}`;
  wrapper.appendChild(title);

  const facultyList = document.createElement("div");
  // נשתמש במחלקת row לכל שורה כדי להיראות כמו בחירת מוסדות
  const faculties = uniqueFaculties(programs);

  // שמירת מצב בחירה למוסד זה
  if (!FACULTY_SELECTIONS[inst]) FACULTY_SELECTIONS[inst] = new Set();

  faculties.forEach((fac, idx) => {
    const row = document.createElement("div"); row.className = "row";
    const id = `fac_${inst}_${idx}`;
    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.id = id; cb.value = fac;

    // restore state
    if (FACULTY_SELECTIONS[inst].has(fac)) cb.checked = true;

    cb.addEventListener("change", () => {
      if (cb.checked) FACULTY_SELECTIONS[inst].add(fac);
      else FACULTY_SELECTIONS[inst].delete(fac);
      renderProgramsForSelectedFaculties(inst, programs, programsArea);
    });

    const label = document.createElement("label");
    label.htmlFor = id; label.textContent = fac;

    row.appendChild(cb); row.appendChild(label);
    facultyList.appendChild(row);
  });

  const programsArea = document.createElement("div");
  programsArea.className = "chips";
  programsArea.style.marginTop = "8px";

  wrapper.appendChild(facultyList);
  wrapper.appendChild(programsArea);
  parent.appendChild(wrapper);

  // initial paint (if יש שיחזור בחירה)
  renderProgramsForSelectedFaculties(inst, programs, programsArea);
}

function renderProgramsForSelectedFaculties(inst, programs, container) {
  clearChildren(container);
  const selectedFacs = FACULTY_SELECTIONS[inst] ? Array.from(FACULTY_SELECTIONS[inst]) : [];

  if (!selectedFacs.length) {
    const info = document.createElement("div");
    info.className = "muted small";
    info.textContent = "סמן/י פקולטה כדי לראות את התארים שלה.";
    container.appendChild(info);
    return;
  }

  programs
    .filter(p => selectedFacs.includes((p.faculty || "").trim()))
    .forEach(p => {
      const chip = document.createElement("div");
      chip.className = "chip";
      chip.textContent = `${p.name} (${p.id})`;
      chip.dataset.programId = p.id;
      chip.dataset.institution = inst;

      if (SELECTED_PROGRAM_IDS.has(p.id)) chip.classList.add("selected");
      chip.onclick = () => {
        chip.classList.toggle("selected");
        if (chip.classList.contains("selected")) SELECTED_PROGRAM_IDS.add(p.id);
        else SELECTED_PROGRAM_IDS.delete(p.id);
      };
      container.appendChild(chip);
    });

  if (!container.childElementCount) {
    const empty = document.createElement("div");
    empty.className = "muted small";
    empty.textContent = "אין תארים בפקולטות שסומנו.";
    container.appendChild(empty);
  }
}

function getSelectedProgramIds() { return Array.from(SELECTED_PROGRAM_IDS.values()); }

/* ================= Compute ================= */
async function onCompute() {
  hideErrors();
  const errors = [];
  const insts = getSelectedInstitutions();
  if (!insts.length) errors.push("יש לבחור לפחות מוסד אחד.");

  const psyRaw = document.getElementById("psy").value;
  if (psyRaw === "") errors.push("יש להזין ציון פסיכומטרי.");
  else {
    const p = parseInt(psyRaw, 10);
    if (isNaN(p) || p < 200 || p > 800) errors.push("ציון פסיכומטרי חייב להיות בין 200 ל־800.");
  }

  const mandatoryRes = readSubjects("mandatory", true);
  const electiveRes  = readSubjects("electives", false);
  errors.push(...mandatoryRes.errors, ...electiveRes.errors);
  if (errors.length) { showErrors(errors); return; }

  const payload = {
    institutions: insts,
    psychometric_total: parseInt(psyRaw, 10),
    subjects: [...mandatoryRes.subjects, ...electiveRes.subjects],
    program_ids: getSelectedProgramIds()
  };

  try {
    const res = await fetch(`${API}/compute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const txt = await res.text();
      showErrors([`שגיאת שרת (${res.status}): ${txt}`]); return;
    }
    const data = await res.json();
    renderResults(data);
  } catch (e) {
    showErrors([`שגיאה בתקשורת: ${e.message}`]);
  }
}

function renderResults(data) {
  const resultsDiv = document.getElementById("results");
  clearChildren(resultsDiv);
  if (!Array.isArray(data) || !data.length) { resultsDiv.textContent = "לא נמצאו תוצאות."; return; }

  data.forEach(p => {
    const card = document.createElement("div"); card.className = "card";
    const status = document.createElement("div");
    status.className = p.passed ? "results-pass" : "results-fail";
    status.textContent = p.passed ? "עבר ✓" : "לא עבר ✗";

    const title = document.createElement("h3");
    const instHeb = hebrewInstitutionName(p.institution || "");
    title.textContent = `${instHeb} – ${p.program_name} (${p.program_id})`;

    const metrics = document.createElement("div");
    const d = safeNumberToFixed(p.D, 2);
    const s = safeNumberToFixed(p.S, 3);
    const t = (p.threshold !== undefined && p.threshold !== null) ? p.threshold : "-";
    const ptext = (p.P !== undefined && p.P !== null) ? String(p.P) : "-";

    metrics.className = "grid small";
    metrics.innerHTML = `
      <div><b>ממוצע בגרויות</b>: ${d}</div>
      <div><b>P</b>: ${ptext}</div>
      <div><b>סכם</b>: ${s}</div>
      <div><b>סף</b>: ${t}</div>
    `;

    const expl = document.createElement("ul");
    (p.explanations || []).forEach(x => { const li = document.createElement("li"); li.textContent = x; expl.appendChild(li); });

    card.appendChild(title); card.appendChild(status); card.appendChild(metrics); card.appendChild(expl);
    resultsDiv.appendChild(card);
  });
}

/* ================= Main ================= */
async function main() {
  await loadDefaultSubjects();
  await loadInstitutions();
  document.getElementById("compute").addEventListener("click", onCompute);
}
main().catch(err => showErrors([`שגיאה באתחול: ${err.message}`]));

const $ = (id) => document.getElementById(id);
const dropzoneInner = $("dropzone-inner");
const fileInput = $("file-input");
const fileStatus = $("file-status");
const errorMessage = $("error-message");
const intake = $("intake");
const loading = $("loading");
const results = $("results");
const resultsFilename = $("results-filename");
const healthPanel = $("health-panel");
const experiencePanel = $("experience-panel");
const atsPanel = $("ats-panel");
const planPanel = $("plan-panel");
const confirmPanel = $("confirm-panel");
const confirmList = $("confirm-list");
const applicationList = $("application-list");
const previewButton = $("preview-resume-button");
const previewPanel = $("resume-preview");
const generateNote = $("generate-note");
const generateError = $("generate-error");
const focusPanel = $("focus-panel");
const focusList = $("focus-list");
const rolesHeading = $("roles-heading");
const roleList = $("role-list");
const interviewPanel = $("interview-panel");
const resetButton = $("reset-button");
const downloadButton = $("download-pdf-button");
const downloadError = $("download-error");
const targetRoleSelect = $("target-role-select");
const jdInputPanel = $("jd-input-panel");
const jobDescription = $("job-description");
const customRoleName = $("custom-role-name");
const customRoleButton = $("save-custom-role");
const customRoleNote = $("custom-role-note");
const deltaPanel = $("delta-panel");
const loadingMessage = $("loading-message");

let currentFile = null;
let lastAnalysisData = null;
let currentMode = "roles";
let pendingEditedData = null;
const APPLICATIONS = window.ROLE_APPLICATIONS || {};

function esc(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

dropzoneInner.addEventListener("click", () => fileInput.click());
dropzoneInner.setAttribute("tabindex", "0");
dropzoneInner.setAttribute("role", "button");
dropzoneInner.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
});
["dragenter", "dragover"].forEach((evt) => dropzoneInner.addEventListener(evt, (e) => {
  e.preventDefault(); dropzoneInner.classList.add("is-dragover");
}));
["dragleave", "drop"].forEach((evt) => dropzoneInner.addEventListener(evt, (e) => {
  e.preventDefault(); dropzoneInner.classList.remove("is-dragover");
}));
dropzoneInner.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});
fileInput.addEventListener("change", () => { if (fileInput.files[0]) handleFile(fileInput.files[0]); });

document.querySelectorAll(".mode-switch__button").forEach((button) => {
  button.addEventListener("click", () => {
    currentMode = button.dataset.mode;
    document.querySelectorAll(".mode-switch__button").forEach((b) => b.classList.toggle("is-active", b === button));
    jdInputPanel.hidden = currentMode !== "jd";
    if (currentMode === "jd") targetRoleSelect.value = "";
    if (currentFile && !results.hidden) uploadFile(currentFile);
  });
});

targetRoleSelect.addEventListener("change", () => {
  const params = new URLSearchParams(location.search);
  if (targetRoleSelect.value) params.set("role", targetRoleSelect.value); else params.delete("role");
  history.replaceState({}, "", `${location.pathname}${params.toString() ? "?" + params : ""}`);
  if (currentFile && !results.hidden) uploadFile(currentFile);
});

function handleFile(file) {
  currentFile = file;
  errorMessage.hidden = true;
  fileStatus.hidden = false;
  fileStatus.textContent = `Selected: ${file.name}`;
  uploadFile(file);
}

function setLoadingStage(stage) {
  const labels = { extract: "Extracting resume text…", detect: "Detecting skills and experience signals…", score: "Scoring role fit and ATS compatibility…", plan: "Building your action plan and interview prep…" };
  loadingMessage.textContent = labels[stage] || "Working…";
  document.querySelectorAll(".loading-steps span").forEach((el) => {
    el.classList.toggle("is-active", el.dataset.step === stage);
  });
}

async function uploadFile(file) {
  const formData = new FormData();
  formData.append("resume", file);
  if (currentMode === "roles") formData.append("target_role", targetRoleSelect.value);
  if (currentMode === "jd") formData.append("job_description", jobDescription.value.trim());

  intake.hidden = true; results.hidden = true; loading.hidden = false;
  setLoadingStage("extract");
  try {
    await new Promise(r => setTimeout(r, 150));
    setLoadingStage("detect");
    await new Promise(r => setTimeout(r, 150));
    setLoadingStage("score");
    const response = await fetch("/analyze", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Something went wrong.");
    setLoadingStage("plan");
    await new Promise(r => setTimeout(r, 150));
    renderResults(data);
  } catch (err) {
    loading.hidden = true; intake.hidden = false;
    errorMessage.hidden = false; errorMessage.textContent = err.message;
  }
}

function tierFor(score) {
  if (score >= 70) return { className: "tier-strong", label: "STRONG FIT" };
  if (score >= 40) return { className: "tier-moderate", label: "MODERATE FIT" };
  return { className: "tier-low", label: "LOW FIT" };
}
function ratingColor(rating) {
  if (rating === "Excellent" || rating === "Good") return "var(--stamp)";
  if (rating === "Needs Work") return "var(--amber)";
  return "var(--error)";
}
function ringSvg(score, radius, strokeColor) {
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - score / 100);
  const size = radius * 2 + 10, center = size / 2;
  return `<svg viewBox="0 0 ${size} ${size}">
    <circle class="ring-track" cx="${center}" cy="${center}" r="${radius}"></circle>
    <circle class="ring-value" cx="${center}" cy="${center}" r="${radius}" stroke="${strokeColor}"
      stroke-dasharray="${circumference}" stroke-dashoffset="${circumference}" data-final-offset="${offset}"></circle>
  </svg>`;
}

function renderHealth(h) {
  healthPanel.innerHTML = `
    <div class="health__item"><p class="health__label">EMAIL</p><p class="health__value ${h.has_email ? "is-good" : "is-bad"}">${h.has_email ? "Found" : "Not found"}</p></div>
    <div class="health__item"><p class="health__label">PHONE</p><p class="health__value ${h.has_phone ? "is-good" : "is-bad"}">${h.has_phone ? "Found" : "Not found"}</p></div>
    <div class="health__item"><p class="health__label">WORD COUNT</p><p class="health__value">${h.word_count}</p></div>
    <div class="health__item"><p class="health__label">SECTIONS</p><p class="health__value">${h.sections_found.length ? h.sections_found.map(esc).join(", ") : "None detected"}</p></div>`;
}
function renderExperience(signal) {
  if (!signal || (signal.level === "unknown" && !signal.years)) { experiencePanel.hidden = true; return; }
  experiencePanel.hidden = false;
  experiencePanel.innerHTML = `<span class="insight-panel__label">EXPERIENCE SIGNAL</span>
    <strong>${esc(signal.level.toUpperCase())}</strong>
    <span>${signal.years != null ? `${signal.years}+ years detected` : "Seniority wording detected"}</span>
    <span class="insight-panel__muted">Used as a small role-fit modifier; it does not replace skills or actual experience.</span>`;
}
function renderAts(ats) {
  const issuesHtml = ats.issues.length ? `<ul class="ats-panel__issues">${ats.issues.map(i => `<li>${esc(i)}</li>`).join("")}</ul>` : `<p class="ats-panel__clean">No major ATS red flags detected.</p>`;
  atsPanel.innerHTML = `<div class="ats-panel__ring">${ringSvg(ats.score, 39, ratingColor(ats.rating))}
    <div class="ats-panel__ring-label"><span class="ats-panel__ring-score">${ats.score}</span><span class="ats-panel__ring-total">/ 100</span></div></div>
    <div class="ats-panel__body"><p class="ats-panel__eyebrow">ATS COMPATIBILITY · ${esc(ats.rating.toUpperCase())}</p>
    <h3 class="ats-panel__title">How well this resume parses for applicant tracking systems</h3>${issuesHtml}</div>`;
}
function renderPlanSection(title, items, emptyText) {
  if (!items || !items.length) return `<div class="plan-section"><p class="plan-section__title">${title}</p><p class="plan-empty">${emptyText}</p></div>`;
  return `<div class="plan-section"><p class="plan-section__title">${title}</p>${items.map(item =>
    `<div class="plan-item"><span class="plan-item__bullet">→</span><span><span class="plan-item__skill">${esc(item.skill)}:</span> <span class="plan-item__tip">${esc(item.tip)}</span></span></div>`).join("")}</div>`;
}
function renderResumeChanges(changes) {
  return `<div class="plan-section"><p class="plan-section__title">RESUME CHANGES TO MAKE</p>${(changes || []).map(c =>
    `<div class="plan-item"><span class="plan-item__bullet">→</span><span class="plan-item__tip">${esc(c)}</span></div>`).join("")}</div>`;
}
function renderTargetPlan(plan) {
  planPanel.hidden = false; focusPanel.hidden = true; rolesHeading.textContent = "Other roles worth a look";
  const req = new Set(plan.matched_required || []), pref = new Set(plan.matched_preferred || []);
  planPanel.innerHTML = `<p class="plan-panel__eyebrow">YOUR PLAN FOR</p><h2 class="plan-panel__title">${esc(plan.role)}</h2>
    <p class="plan-panel__score">${plan.score}% fit · Required skills carry ${plan.skill_weights?.required || 100}% of the role score</p>
    <div class="plan-panel__skills">${plan.matched_skills.map(s => `<span class="skill-tag matched">${esc(s)}${req.has(s) ? " · R" : pref.has(s) ? " · P" : ""}</span>`).join("")}
      ${plan.missing_skills.map(s => `<span class="skill-tag missing">${esc(s)}${(plan.missing_required || []).includes(s) ? " · R" : " · P"}</span>`).join("")}</div>
    ${renderPlanSection("SKILLS TO DEVELOP", plan.skill_development, "No technical gaps — your skills already line up.")}
    ${renderPlanSection("PERSONAL DEVELOPMENT", plan.personal_development, "No behavioral gaps found for this role.")}
    ${renderResumeChanges(plan.resume_changes)}`;
  renderConfirmPanel(plan);
  renderInterviewPrep(plan);
}
function renderFocusSkills(focusSkills) {
  planPanel.hidden = true; confirmPanel.hidden = true; previewPanel.hidden = true;
  focusPanel.hidden = !(focusSkills && focusSkills.length);
  if (focusSkills && focusSkills.length) focusList.innerHTML = focusSkills.map((item, i) =>
    `<li class="focus-item"><span class="focus-item__rank">${String(i + 1).padStart(2, "0")}</span><div class="focus-item__body"><p class="focus-item__skill">${esc(item.skill)}</p><p class="focus-item__helps">Helps with: ${item.helps_with.map(esc).join(", ")}</p></div></li>`).join("");
  rolesHeading.textContent = "Where you're the strongest fit";
  interviewPanel.hidden = true;
}
function renderConfirmPanel(plan) {
  const missing = plan.missing_skills || [];
  confirmPanel.hidden = !missing.length;
  if (!missing.length) return;
  confirmList.innerHTML = missing.map((skill, i) => `<label class="confirm-item"><input type="checkbox" value="${esc(skill)}" id="confirm-${i}">${esc(skill)}</label>`).join("");
  applicationList.innerHTML = "";
  generateError.hidden = true; generateNote.hidden = true; previewPanel.hidden = true;
  confirmList.querySelectorAll("input").forEach(cb => cb.addEventListener("change", renderApplicationChoices));
}
function renderApplicationChoices() {
  const selected = getConfirmedSkills();
  applicationList.innerHTML = selected.map(skill => {
    const options = APPLICATIONS[skill] || [];
    if (!options.length) return `<div class="application-item"><strong>${esc(skill)}</strong><input class="text-input text-input--small app-custom" data-skill="${esc(skill)}" placeholder="Application/tool you used"></div>`;
    return `<div class="application-item"><strong>${esc(skill)}</strong><div class="application-options">${options.map((a, i) =>
      `<label><input type="checkbox" data-skill="${esc(skill)}" value="${esc(a)}" class="app-check"> ${esc(a)}</label>`).join("")}</div>
      <input class="text-input text-input--small app-custom" data-skill="${esc(skill)}" placeholder="Other application/tool"></div>`;
  }).join("");
}
function renderInterviewPrep(plan) {
  const qs = plan.interview_questions || {};
  const skills = Object.keys(qs);
  if (!skills.length) { interviewPanel.hidden = true; return; }
  interviewPanel.hidden = false;
  interviewPanel.innerHTML = `<p class="focus-panel__eyebrow">INTERVIEW PREP</p><h3 class="focus-panel__title">Likely questions for your skill gaps</h3>
    ${skills.slice(0, 8).map(s => `<details><summary>${esc(s)}</summary><ol>${qs[s].map(q => `<li>${esc(q)}</li>`).join("")}</ol></details>`).join("")}`;
}
function renderRoleList(roles) {
  roleList.innerHTML = "";
  if (!roles.length) {
    roleList.innerHTML = `<li class="empty-state">No role matches were found. Try a text-based resume or paste a fuller job description.</li>`;
    return;
  }
  roles.forEach((role, i) => {
    const tier = tierFor(role.score), req = new Set(role.matched_required || []);
    const li = document.createElement("li");
    li.className = `role-card ${tier.className}`; li.style.setProperty("--card-delay", `${i * 0.06}s`);
    li.innerHTML = `<div class="role-card__ring">${ringSvg(role.score, 27, "currentColor")}<span class="role-card__ring-label">${role.score}%</span></div>
      <div class="role-card__main"><div class="role-card__top"><h3 class="role-card__title">${esc(role.role)}</h3><span class="role-card__tier-label">${tier.label}</span></div>
      <p class="role-card__description">${esc(role.description)}</p><div class="role-card__skills">
      ${role.matched_skills.map(s => `<span class="skill-tag matched">${esc(s)}${req.has(s) ? " · R" : " · P"}</span>`).join("")}
      ${role.missing_skills.map(s => `<span class="skill-tag missing">${esc(s)}${(role.missing_required || []).includes(s) ? " · R" : " · P"}</span>`).join("")}</div></div>`;
    roleList.appendChild(li);
  });
}
function renderDelta(data) {
  const key = `role-finder:${data.filename || "resume"}`;
  const previous = JSON.parse(localStorage.getItem(key) || "null");
  if (previous && typeof previous.score === "number") {
    const delta = +(data.ats.score - previous.score).toFixed(1);
    const skillDelta = (data.detected_skills || []).filter(s => !(previous.skills || []).includes(s));
    deltaPanel.hidden = false;
    deltaPanel.textContent = `${delta >= 0 ? "▲" : "▼"} ${Math.abs(delta)} ATS points since last analysis · ${skillDelta.length} newly detected skill${skillDelta.length === 1 ? "" : "s"}`;
  } else deltaPanel.hidden = true;
  localStorage.setItem(key, JSON.stringify({ score: data.ats.score, skills: data.detected_skills || [], timestamp: Date.now() }));
}
function renderResults(data) {
  loading.hidden = true; results.hidden = false; lastAnalysisData = data; pendingEditedData = null;
  resultsFilename.textContent = data.filename;
  renderDelta(data); renderHealth(data.health); renderExperience(data.experience_signal); renderAts(data.ats);
  if (data.target_plan) renderTargetPlan(data.target_plan); else renderFocusSkills(data.focus_skills);
  renderRoleList(data.roles);
  requestAnimationFrame(() => document.querySelectorAll(".ring-value").forEach(c => c.style.strokeDashoffset = c.dataset.finalOffset));
}

resetButton.addEventListener("click", () => {
  fileInput.value = ""; currentFile = null; lastAnalysisData = null; pendingEditedData = null;
  fileStatus.hidden = true; results.hidden = true; intake.hidden = false; confirmPanel.hidden = true; previewPanel.hidden = true;
});
downloadButton.addEventListener("click", async () => {
  if (!lastAnalysisData) return;
  downloadButton.disabled = true; downloadButton.textContent = "Preparing PDF…"; downloadError.hidden = true;
  try {
    const response = await fetch("/download-report", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(lastAnalysisData) });
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || "Could not generate the PDF.");
    const blob = await response.blob(), url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = `role_finder_report_${(lastAnalysisData.filename || "resume").replace(/\.[^.]+$/, "")}.pdf`;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  } catch (err) { downloadError.hidden = false; downloadError.textContent = err.message; }
  finally { downloadButton.disabled = false; downloadButton.textContent = "Download PDF Report"; }
});
function getConfirmedSkills() {
  return Array.from(confirmList.querySelectorAll("input[type='checkbox']:checked")).map(cb => cb.value);
}
function getApplications() {
  const result = {};
  getConfirmedSkills().forEach(skill => {
    result[skill] = Array.from(applicationList.querySelectorAll(`.app-check[data-skill="${CSS.escape(skill)}"]:checked`)).map(x => x.value);
    const custom = applicationList.querySelector(`.app-custom[data-skill="${CSS.escape(skill)}"]`);
    if (custom && custom.value.trim()) result[skill].push(custom.value.trim());
  });
  return result;
}
function editorPayload(format=null) {
  return {
    resume_text: lastAnalysisData.resume_text,
    matched_skills: lastAnalysisData.target_plan.matched_skills,
    confirmed_skills: getConfirmedSkills(),
    applications: getApplications(),
    filename: lastAnalysisData.filename,
    format
  };
}
previewButton.addEventListener("click", async () => {
  if (!lastAnalysisData?.target_plan) return;
  previewButton.disabled = true; previewButton.textContent = "Building preview…"; generateError.hidden = true;
  try {
    const response = await fetch("/preview-resume", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(editorPayload())});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || "Could not build preview.");
    pendingEditedData = editorPayload();
    const d = data.diff || {};
    previewPanel.hidden = false;
    previewPanel.innerHTML = `<p class="confirm-panel__eyebrow">DIFF / PREVIEW</p><h3 class="confirm-panel__title">Review before download</h3>
      <div class="preview-grid"><div><p class="preview-label">SUMMARY BEFORE</p><div class="preview-copy">${esc(d.summary_before || "No summary detected.")}</div></div>
      <div><p class="preview-label">SUMMARY AFTER</p><div class="preview-copy preview-copy--after">${esc(d.summary_after || "No summary will be added.")}</div></div></div>
      <p class="preview-label">CONFIRMED APPLICATIONS</p><div class="preview-apps">${Object.entries(d.applications || {}).flatMap(([s, apps]) => apps.map(a => `<span class="skill-tag preferred">${esc(s)} → ${esc(a)}</span>`)).join("") || "None selected"}</div>
      <div class="generate-actions"><button id="final-pdf" class="download-button" type="button">Confirm & Download PDF</button><button id="final-docx" class="download-button download-button--secondary" type="button">Confirm & Download Word</button></div>`;
    $("final-pdf").addEventListener("click", () => generateResume("pdf"));
    $("final-docx").addEventListener("click", () => generateResume("docx"));
  } catch (err) { generateError.hidden = false; generateError.textContent = err.message; }
  finally { previewButton.disabled = false; previewButton.textContent = "Preview Changes"; }
});
async function generateResume(format) {
  if (!pendingEditedData) return;
  const buttons = [$("final-pdf"), $("final-docx")].filter(Boolean);
  buttons.forEach(b => b.disabled = true);
  generateError.hidden = true;
  try {
    const payload = {...pendingEditedData, format};
    const response = await fetch("/generate-resume", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || "Could not generate the resume.");
    const blob = await response.blob(), url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = `${(lastAnalysisData.filename || "resume").replace(/\.[^.]+$/, "")}_improved_resume.${format}`;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    generateNote.hidden = false; generateNote.textContent = `Confirmed. ${format.toUpperCase()} resume generated with your selected skills, applications and updated Summary.`;
  } catch (err) { generateError.hidden = false; generateError.textContent = err.message; }
  finally { buttons.forEach(b => b.disabled = false); }
}
customRoleButton.addEventListener("click", async () => {
  const name = customRoleName.value.trim(), jd = jobDescription.value.trim();
  if (!name || !jd) { customRoleNote.hidden = false; customRoleNote.textContent = "Enter a role name and paste a job description first."; return; }
  customRoleButton.disabled = true;
  try {
    const response = await fetch("/custom-role", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({role_name:name, job_description:jd})});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || "Could not save the role.");
    const option = new Option(data.role, data.role); targetRoleSelect.add(option); targetRoleSelect.value = data.role;
    currentMode = "roles"; document.querySelectorAll(".mode-switch__button").forEach(b => b.classList.toggle("is-active", b.dataset.mode === "roles"));
    jdInputPanel.hidden = true;
    customRoleNote.hidden = false; customRoleNote.textContent = `Saved "${data.role}" with ${data.skills.length} recognized skills.`;
  } catch (err) { customRoleNote.hidden = false; customRoleNote.textContent = err.message; }
  finally { customRoleButton.disabled = false; }
});

// Restore role from URL query string.
const initialRole = new URLSearchParams(location.search).get("role");
if (initialRole && Array.from(targetRoleSelect.options).some(o => o.value === initialRole)) targetRoleSelect.value = initialRole;

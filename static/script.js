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
const manualSkillInput = $("manual-skill-input");
const addManualSkillButton = $("add-manual-skill");
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
  confirmPanel.hidden = false;
  confirmList.innerHTML = missing.map((skill, i) => `<label class="confirm-item"><input type="checkbox" value="${esc(skill)}" id="confirm-${i}">${esc(skill)}</label>`).join("");
  if (!missing.length) confirmList.innerHTML = `<p class="plan-empty">No missing role skills detected. You can still choose how to handle your Summary.</p>`;
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
  errorMessage.hidden = true; errorMessage.textContent = "";
  downloadError.hidden = true; downloadError.textContent = "";
  generateError.hidden = true; generateError.textContent = "";
  generateNote.hidden = true; generateNote.textContent = "";
  customRoleNote.hidden = true; customRoleNote.textContent = "";
  focusPanel.hidden = true; planPanel.hidden = true; interviewPanel.hidden = true; deltaPanel.hidden = true;
  if (jobDescription) jobDescription.value = "";
  if (customRoleName) customRoleName.value = "";
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
function getSummaryMode() {
  return document.querySelector("input[name='summary-mode']:checked")?.value || "update";
}
function editorPayload(format=null) {
  if (!lastAnalysisData) return { resume_text: "", matched_skills: [], confirmed_skills: [], applications: {}, filename: "resume", format };

  const targetPlan = lastAnalysisData.target_plan || { matched_skills: [] };
  return {
    resume_text: lastAnalysisData.resume_text || "",
    matched_skills: targetPlan.matched_skills || [],
    confirmed_skills: getConfirmedSkills(),
    applications: getApplications(),
    summary_mode: getSummaryMode(),
    role_name: targetPlan.role || "",
    experience_signal: lastAnalysisData.experience_signal?.level || "",
    filename: lastAnalysisData.filename || "resume",
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
    const resume = data.resume || {preamble: [], sections: []};
    const resumeHtml = [
      ...(resume.preamble || []).map((line, index) => `<p class="${index === 0 ? "resume-paper__name" : "resume-paper__contact"}">${esc(line)}</p>`),
      ...(resume.sections || []).map(([heading, lines]) => `<section class="resume-paper__section"><h4>${esc(heading)}</h4>${(lines || []).filter(Boolean).map(line => `<p>${esc(line)}</p>`).join("")}</section>`)
    ].join("");
    previewPanel.hidden = false;
    previewPanel.innerHTML = `<p class="confirm-panel__eyebrow">DIFF / PREVIEW</p><h3 class="confirm-panel__title">Review before download</h3>
      <p class="preview-label">FULL RESUME OUTPUT</p><div class="resume-paper">${resumeHtml || "<p>No resume content could be previewed.</p>"}</div>
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

function addManualSkill() {
  const value = manualSkillInput.value.trim();
  if (!value) return;
  const existing = Array.from(confirmList.querySelectorAll("input")).some(input => input.value.toLowerCase() === value.toLowerCase());
  if (existing) { manualSkillInput.value = ""; return; }
  const id = `manual-skill-${Date.now()}`;
  const label = document.createElement("label");
  label.className = "confirm-item";
  label.innerHTML = `<input type="checkbox" value="${esc(value)}" id="${id}" checked>${esc(value)}`;
  confirmList.appendChild(label);
  label.querySelector("input").addEventListener("change", renderApplicationChoices);
  manualSkillInput.value = "";
  renderApplicationChoices();
}
addManualSkillButton.addEventListener("click", addManualSkill);
manualSkillInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") { event.preventDefault(); addManualSkill(); }
});

// Restore role from URL query string.
const initialRole = new URLSearchParams(location.search).get("role");
if (initialRole && Array.from(targetRoleSelect.options).some(o => o.value === initialRole)) targetRoleSelect.value = initialRole;

/* =========================================================
   ATS RESUME BUILDER
========================================================= */

let atsExperienceCount = 0;
let atsEducationCount = 0;
let atsProjectCount = 0;
let atsSkillCount = 0;
let atsCertificationCount = 0;
let atsAchievementCount = 0;
let atsPreviewSignature = null;

function bindATSBuilderActions() {
    const openButton = document.getElementById("open-ats-builder");
    if (openButton && !openButton.dataset.bound) {
        openButton.dataset.bound = "true";
        openButton.addEventListener("click", openATSResumeBuilder);
    }

    const closeButton = document.getElementById("close-ats-builder");
    if (closeButton && !closeButton.dataset.bound) {
        closeButton.dataset.bound = "true";
        closeButton.addEventListener("click", closeATSResumeBuilder);
    }

    const cancelButton = document.getElementById("cancel-ats-builder");
    if (cancelButton && !cancelButton.dataset.bound) {
        cancelButton.dataset.bound = "true";
        cancelButton.addEventListener("click", closeATSResumeBuilder);
    }

    const overlay = document.getElementById("ats-modal-overlay");
    if (overlay && !overlay.dataset.bound) {
        overlay.dataset.bound = "true";
        overlay.addEventListener("click", closeATSResumeBuilder);
    }

    const importInput = document.getElementById("ats-import-resume");
    if (importInput && !importInput.dataset.bound) {
        importInput.dataset.bound = "true";
        importInput.addEventListener("change", importExistingATSResume);
    }

    const languageField = document.getElementById("ats-languages");
    if (languageField && !languageField.dataset.bound) {
        languageField.dataset.bound = "true";
        languageField.addEventListener("change", renderSelectedLanguages);
    }
    const addLanguageButton = document.getElementById("add-ats-language");
    if (addLanguageButton && !addLanguageButton.dataset.bound) {
        addLanguageButton.dataset.bound = "true";
        addLanguageButton.addEventListener("click", addCustomATSLanguage);
    }
    const customLanguageInput = document.getElementById("ats-custom-language");
    if (customLanguageInput && !customLanguageInput.dataset.bound) {
        customLanguageInput.dataset.bound = "true";
        customLanguageInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                addCustomATSLanguage();
            }
        });
    }

    const addSkillButton = document.getElementById("add-ats-skill");
    if (addSkillButton && !addSkillButton.dataset.bound) {
        addSkillButton.dataset.bound = "true";
        addSkillButton.addEventListener("click", addATSSkill);
    }

    function renderSelectedLanguages() {
        const languageField = document.getElementById("ats-languages");
        const list = document.getElementById("ats-selected-languages");
        if (!languageField || !list) return;
        list.innerHTML = "";
        [...languageField.querySelectorAll("input[type='checkbox']:checked")].forEach((input) => {
            const tag = document.createElement("span");
            tag.className = "selected-language";
            tag.textContent = input.value;
            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "selected-language__remove";
            remove.setAttribute("aria-label", `Remove ${input.value}`);
            remove.textContent = "×";
            remove.addEventListener("click", () => {
                input.checked = false;
                renderSelectedLanguages();
            });
            tag.appendChild(remove);
            list.appendChild(tag);
        });
    }

    function addLanguageOption(value) {
        const languageField = document.getElementById("ats-languages");
        if (!languageField || !value) return null;
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.value = value;
        label.append(input, ` ${value}`);
        languageField.appendChild(label);
        input.addEventListener("change", renderSelectedLanguages);
        return input;
    }

    function addCustomATSLanguage() {
        const textInput = document.getElementById("ats-custom-language");
        const languageField = document.getElementById("ats-languages");
        if (!textInput || !languageField) return;
        const value = textInput.value.trim();
        if (!value) return;
        let checkbox = [...languageField.querySelectorAll("input[type='checkbox']")]
            .find((candidate) => candidate.value.toLowerCase() === value.toLowerCase());
        if (!checkbox) {
            checkbox = addLanguageOption(value);
        }
        checkbox.checked = true;
        textInput.value = "";
        renderSelectedLanguages();
    }

    async function importExistingATSResume(event) {
        const file = event.target.files?.[0];
        const status = document.getElementById("ats-import-status");
        if (!file) return;
        if (status) {
            status.hidden = false;
            status.textContent = "Reading your resume…";
        }

        const formData = new FormData();
        formData.append("resume", file);
        try {
            const response = await fetch("/import-resume", { method: "POST", body: formData });
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(result.error || "Could not import this resume.");
            populateATSBuilder(result.resume || {});
            if (status) status.textContent = `${result.filename || file.name} imported. Review and edit the fields before previewing.`;
        } catch (error) {
            if (status) status.textContent = error.message;
        } finally {
            event.target.value = "";
        }
    }

    function setATSField(id, value) {
        const field = document.getElementById(id);
        if (field && value) field.value = value;
    }

    function populateATSBuilder(resume) {
        const personal = resume.personal || {};
        setATSField("ats-name", personal.name);
        setATSField("ats-email", personal.email);
        setATSField("ats-phone", personal.phone);
        setATSField("ats-location", personal.location);
        setATSField("ats-linkedin", personal.linkedin);
        setATSField("ats-website", personal.portfolio);
        setATSField("ats-summary", resume.summary);
        const languageField = document.getElementById("ats-languages");
        if (languageField) {
            const importedLanguages = resume.languages || [];
            const selectedLanguages = new Set(importedLanguages.map((language) => language.toLowerCase()));
            importedLanguages.forEach((language) => {
                if (language && ![...languageField.querySelectorAll("input")].some((input) => input.value.toLowerCase() === language.toLowerCase())) {
                    addLanguageOption(language);
                }
            });
            [...languageField.querySelectorAll("input[type='checkbox']")].forEach((input) => {
                input.checked = selectedLanguages.has(input.value.toLowerCase());
            });
            renderSelectedLanguages();
        }

        const experience = document.getElementById("ats-experience-list");
        if (experience && resume.experience?.length) {
            experience.innerHTML = "";
            atsExperienceCount = 0;
            resume.experience.forEach(() => addATSExperience());
            [...experience.querySelectorAll(".builder-repeat-card")].forEach((card, index) => {
                const item = resume.experience[index] || {};
                card.querySelector(".ats-job-title").value = item.job_title || "";
                card.querySelector(".ats-company").value = item.company || "";
                card.querySelector(".ats-exp-location").value = item.location || "";
                card.querySelector(".ats-start-date").value = item.start_date || "";
                card.querySelector(".ats-end-date").value = item.end_date || "";
                card.querySelector(".ats-exp-description").value = item.description || "";
            });
        }

        const education = document.getElementById("ats-education-list");
        if (education && resume.education?.length) {
            education.innerHTML = "";
            atsEducationCount = 0;
            resume.education.forEach(() => addATSEducation());
            [...education.querySelectorAll(".builder-repeat-card")].forEach((card, index) => {
                const item = resume.education[index] || {};
                card.querySelector(".ats-degree").value = item.degree || "";
                card.querySelector(".ats-institution").value = item.institution || "";
                card.querySelector(".ats-edu-location").value = item.location || "";
                card.querySelector(".ats-edu-start").value = item.start_date || "";
                card.querySelector(".ats-edu-end").value = item.end_date || "";
                card.querySelector(".ats-grade").value = item.grade || "";
            });
        }

        const projects = document.getElementById("ats-projects-list");
        if (projects && resume.projects?.length) {
            projects.innerHTML = "";
            atsProjectCount = 0;
            resume.projects.forEach(() => addATSProject());
            [...projects.querySelectorAll(".builder-repeat-card")].forEach((card, index) => {
                const item = resume.projects[index] || {};
                card.querySelector(".ats-project-name").value = item.name || "";
                card.querySelector(".ats-project-description").value = item.description || "";
                card.querySelector(".ats-project-technologies").value = (item.technologies || []).join(", ");
            });
        }

        const skills = document.getElementById("ats-skills-list");
        if (skills && resume.skills?.length) {
            skills.innerHTML = "";
            atsSkillCount = 0;
            resume.skills.forEach(() => addATSSkill());
            [...skills.querySelectorAll(".ats-skill")].forEach((field, index) => {
                field.value = resume.skills[index] || "";
            });
        }

        const certifications = document.getElementById("ats-certifications-list");
        if (certifications && resume.certifications?.length) {
            certifications.innerHTML = "";
            atsCertificationCount = 0;
            resume.certifications.forEach(() => addATSCertification());
            [...certifications.querySelectorAll(".ats-certification")].forEach((field, index) => {
                field.value = resume.certifications[index] || "";
            });
        }

        const achievements = document.getElementById("ats-achievements-list");
        if (achievements && resume.achievements?.length) {
            achievements.innerHTML = "";
            atsAchievementCount = 0;
            resume.achievements.forEach(() => addATSAchievement());
            [...achievements.querySelectorAll(".ats-achievement")].forEach((field, index) => {
                field.value = resume.achievements[index] || "";
            });
        }
    }

    const addExperienceButton = document.getElementById("add-ats-experience");
    if (addExperienceButton && !addExperienceButton.dataset.bound) {
        addExperienceButton.dataset.bound = "true";
        addExperienceButton.addEventListener("click", addATSExperience);
    }

    const addEducationButton = document.getElementById("add-ats-education");
    if (addEducationButton && !addEducationButton.dataset.bound) {
        addEducationButton.dataset.bound = "true";
        addEducationButton.addEventListener("click", addATSEducation);
    }

    const addProjectButton = document.getElementById("add-ats-project");
    if (addProjectButton && !addProjectButton.dataset.bound) {
        addProjectButton.dataset.bound = "true";
        addProjectButton.addEventListener("click", addATSProject);
    }

    const addCertificationButton = document.getElementById("add-ats-certification");
    if (addCertificationButton && !addCertificationButton.dataset.bound) {
        addCertificationButton.dataset.bound = "true";
        addCertificationButton.addEventListener("click", addATSCertification);
    }

    const addAchievementButton = document.getElementById("add-ats-achievement");
    if (addAchievementButton && !addAchievementButton.dataset.bound) {
        addAchievementButton.dataset.bound = "true";
        addAchievementButton.addEventListener("click", addATSAchievement);
    }

    const autoSummaryButton = document.getElementById("auto-generate-summary");
    if (autoSummaryButton && !autoSummaryButton.dataset.bound) {
        autoSummaryButton.dataset.bound = "true";
        autoSummaryButton.addEventListener("click", () => {
            const summaryField = document.getElementById("ats-summary");
            if (!summaryField) return;
            summaryField.value = generateATSProfessionalSummary(collectATSResumeData());
            summaryField.focus();
        });
    }

    const autoJobButton = document.getElementById("auto-generate-target-job");
    if (autoJobButton && !autoJobButton.dataset.bound) {
        autoJobButton.dataset.bound = "true";
        autoJobButton.addEventListener("click", () => {
            const jobField = document.getElementById("ats-job-description");
            if (!jobField) return;
            jobField.value = generateATSTargetJobDescription(collectATSResumeData());
            jobField.focus();
        });
    }

    const previewBtn = document.getElementById("preview-ats-resume");
    if (previewBtn && !previewBtn.dataset.bound) {
        previewBtn.dataset.bound = "true";
        previewBtn.addEventListener("click", previewATSResume);
    }

    const pdfButton = document.getElementById("download-ats-pdf");
    if (pdfButton && !pdfButton.dataset.bound) {
        pdfButton.dataset.bound = "true";
        pdfButton.addEventListener("click", () => downloadATSResume("pdf"));
    }

    const docxButton = document.getElementById("download-ats-docx");
    if (docxButton && !docxButton.dataset.bound) {
        docxButton.dataset.bound = "true";
        docxButton.addEventListener("click", () => downloadATSResume("docx"));
    }
}

function dedupeList(values) {
    return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function inferATSRole(skills) {
    const normalized = skills.join(" ").toLowerCase();

    const roleMap = [
        { pattern: /(python|java|javascript|react|node|sql|api|software|aws|azure|docker|kubernetes)/, title: "Software Engineer" },
        { pattern: /(power bi|powerbi|excel|tableau|data analysis|analytics|sql|dashboard|reporting)/, title: "Data Analyst" },
        { pattern: /(finance|accounting|bookkeeping|reconciliation|audit|tax|budget|financial)/, title: "Finance Professional" },
        { pattern: /(sales|marketing|crm|business development|customer acquisition|lead generation|branding)/, title: "Sales and Marketing Professional" },
        { pattern: /(hr|human resources|recruitment|talent|employee relations|onboarding)/, title: "HR Professional" },
        { pattern: /(project management|jira|agile|stakeholder|planning|operations|process improvement)/, title: "Project or Operations Professional" },
        { pattern: /(customer service|support|help desk|troubleshooting|service desk|client support)/, title: "Customer Support Professional" },
    ];

    for (const entry of roleMap) {
        if (entry.pattern.test(normalized)) return entry.title;
    }

    return "Professional";
}

function generateATSProfessionalSummary(resume) {
    const personal = resume?.personal || {};
    const skills = dedupeList([...(resume?.skills || []), ...(resume?.projects || []).flatMap((project) => project.technologies || []), ...(resume?.achievements || [])]);
    const firstEducation = (resume?.education || [])[0] || {};
    const experienceEntries = resume?.experience || [];
    const topSkills = skills.slice(0, 8).join(", ");
    const roleTitle = inferATSRole(skills);
    const educationText = firstEducation.degree || firstEducation.institution ?
        `Academic background includes ${[firstEducation.degree, firstEducation.institution].filter(Boolean).join(" from ")}.` :
        "";
    const experienceText = experienceEntries.length ?
        `Experience includes work across ${experienceEntries.map((entry) => entry.job_title || "core business operations").filter(Boolean).slice(0, 2).join(" and ")}.` :
        "";

    const summaryParts = [
        `Results-driven ${roleTitle} with strong experience in ${topSkills || "core business functions"}.`,
        `Skilled in delivering practical solutions, improving processes, and supporting organizational goals through effective communication, problem-solving, and collaboration.`,
    ];

    if (educationText) summaryParts.push(educationText);
    if (experienceText) summaryParts.push(experienceText);

    return summaryParts.join(" ").replace(/\s+/g, " ").trim();
}

function generateATSTargetJobDescription(resume) {
    const skills = dedupeList(resume?.skills || []);
    const roleTitle = inferATSRole(skills);
    const topSkills = skills.slice(0, 7).join(", ");
    const responsibilities = [
        "support day-to-day operations and ensure high-quality execution",
        "improve workflows, documentation, and process efficiency",
        "collaborate with stakeholders to deliver business-focused outcomes",
        "identify and resolve issues using analytical and technical problem-solving skills",
    ];

    const coreText = topSkills ? `with expertise in ${topSkills}` : "with a strong focus on operational excellence";

    return [
        `Seeking a ${roleTitle} opportunity to contribute ${coreText}.`,
        `The ideal candidate will be responsible for ${responsibilities[0]}, ${responsibilities[1]}, and ${responsibilities[2]}.`,
        `This role requires strong communication, attention to detail, and the ability to apply technical and business knowledge effectively to support team goals and improve performance.`,
    ].join(" ").replace(/\s+/g, " ").trim();
}

/* ---------------------------------------------------------
   OPEN / CLOSE
--------------------------------------------------------- */

function openATSResumeBuilder() {
    const modal = document.getElementById("atsResumeModal");
    if (!modal) return;
    modal.hidden = false;
    modal.style.display = "flex";
    bindATSBuilderActions();
    initializeATSBuilder();
}

function closeATSResumeBuilder() {
    const modal = document.getElementById("atsResumeModal");
    if (!modal) return;
    modal.hidden = true;
    modal.style.display = "none";

    const builderForm = document.getElementById("ats-resume-builder-form");
    if (builderForm) builderForm.reset();

    const resultPanel = document.getElementById("atsScorePanel");
    if (resultPanel) { resultPanel.hidden = true; resultPanel.style.display = "none"; }

    const errorBox = document.getElementById("ats-builder-error");
    if (errorBox) { errorBox.hidden = true; errorBox.textContent = ""; }
    atsPreviewSignature = null;
    setATSDownloadState(false);
}

function atsResumeSignature(resume) {
    return JSON.stringify(resume);
}

function setATSDownloadState(enabled) {
    ["download-ats-pdf", "download-ats-docx"].forEach((id) => {
        const button = document.getElementById(id);
        if (button) button.disabled = !enabled;
    });
}

/* ---------------------------------------------------------
   INITIALIZE — clears each list and seeds it with one
   JS-generated row, so every visible field is one the data
   collector below actually knows how to read.
--------------------------------------------------------- */

function initializeATSBuilder() {
    atsPreviewSignature = null;
    setATSDownloadState(false);
    const languageField = document.getElementById("ats-languages");
    if (languageField) {
        [...languageField.querySelectorAll("input[type='checkbox']")].forEach((input) => { input.checked = false; });
    }
    const selectedLanguages = document.getElementById("ats-selected-languages");
    if (selectedLanguages) selectedLanguages.innerHTML = "";
    const customLanguage = document.getElementById("ats-custom-language");
    if (customLanguage) customLanguage.value = "";
    const skills = document.getElementById("ats-skills-list");
    if (skills) { skills.innerHTML = ""; addATSSkill(); addATSSkill(); addATSSkill(); }

    const experience = document.getElementById("ats-experience-list");
    if (experience) { experience.innerHTML = ""; addATSExperience(); }

    const education = document.getElementById("ats-education-list");
    if (education) { education.innerHTML = ""; addATSEducation(); }

    const projects = document.getElementById("ats-projects-list");
    if (projects) { projects.innerHTML = ""; addATSProject(); }

    const certifications = document.getElementById("ats-certifications-list");
    if (certifications) { certifications.innerHTML = ""; addATSCertification(); }

    const achievements = document.getElementById("ats-achievements-list");
    if (achievements) { achievements.innerHTML = ""; addATSAchievement(); }
}

/* ---------------------------------------------------------
   SKILLS
   Note: collectATSResumeData() reads these by class (".ats-skill"),
   so adding id/for/autocomplete here is safe and doesn't require
   any change to the data-collection logic below.
--------------------------------------------------------- */

function addATSSkill() {
    atsSkillCount++;
    const container = document.getElementById("ats-skills-list");
    if (!container) return;
    const uid = `ats-skill-${atsSkillCount}`;
    const wrapper = document.createElement("div");
    wrapper.className = "builder-list-item";
    wrapper.innerHTML = `
        <label for="${uid}" class="visually-hidden">Skill</label>
        <input id="${uid}" type="text" class="ats-skill" placeholder="Skill" autocomplete="off">
        <button type="button" class="remove-builder-item" aria-label="Remove skill" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(wrapper);
}

/* ---------------------------------------------------------
   EXPERIENCE
--------------------------------------------------------- */

function addATSExperience() {
    atsExperienceCount++;
    const container = document.getElementById("ats-experience-list");
    if (!container) return;
    const n = atsExperienceCount;
    const wrapper = document.createElement("div");
    wrapper.className = "builder-repeat-card";
    wrapper.innerHTML = `
        <div class="repeat-card-header">
            <strong>Experience ${n}</strong>
            <button type="button" class="remove-button" onclick="this.parentElement.parentElement.remove()">Remove</button>
        </div>
        <div class="builder-grid">
            <div class="builder-field">
                <label for="exp-title-${n}">Job Title</label>
                <input id="exp-title-${n}" class="ats-job-title" type="text" placeholder="Technical Support Engineer" autocomplete="organization-title">
            </div>
            <div class="builder-field">
                <label for="exp-company-${n}">Company</label>
                <input id="exp-company-${n}" class="ats-company" type="text" placeholder="Company" autocomplete="organization">
            </div>
            <div class="builder-field">
                <label for="exp-location-${n}">Location</label>
                <input id="exp-location-${n}" class="ats-exp-location" type="text" placeholder="Location" autocomplete="off">
            </div>
            <div class="builder-field">
                <label for="exp-start-${n}">Start Date</label>
                <input id="exp-start-${n}" class="ats-start-date" type="text" placeholder="Start Date" autocomplete="off">
            </div>
            <div class="builder-field">
                <label for="exp-end-${n}">End Date / Present</label>
                <input id="exp-end-${n}" class="ats-end-date" type="text" placeholder="End Date / Present" autocomplete="off">
            </div>
        </div>
        <div class="builder-field">
            <label for="exp-desc-${n}">Responsibilities and achievements</label>
            <textarea id="exp-desc-${n}" class="ats-exp-description" rows="5" placeholder="Responsibilities and achievements. Use one bullet per line." autocomplete="off"></textarea>
        </div>
    `;
    container.appendChild(wrapper);
}

/* ---------------------------------------------------------
   EDUCATION
--------------------------------------------------------- */

function addATSEducation() {
    atsEducationCount++;
    const container = document.getElementById("ats-education-list");
    if (!container) return;
    const n = atsEducationCount;
    const wrapper = document.createElement("div");
    wrapper.className = "builder-repeat-card";
    wrapper.innerHTML = `
        <div class="repeat-card-header">
            <strong>Education ${n}</strong>
            <button type="button" class="remove-button" onclick="this.parentElement.parentElement.remove()">Remove</button>
        </div>
        <div class="builder-grid">
            <div class="builder-field">
                <label for="edu-degree-${n}">Degree</label>
                <input id="edu-degree-${n}" class="ats-degree" type="text" placeholder="Degree" autocomplete="off">
            </div>
            <div class="builder-field">
                <label for="edu-institution-${n}">Institution</label>
                <input id="edu-institution-${n}" class="ats-institution" type="text" placeholder="Institution" autocomplete="off">
            </div>
            <div class="builder-field">
                <label for="edu-location-${n}">Location</label>
                <input id="edu-location-${n}" class="ats-edu-location" type="text" placeholder="Location" autocomplete="off">
            </div>
            <div class="builder-field">
                <label for="edu-start-${n}">Start Date</label>
                <input id="edu-start-${n}" class="ats-edu-start" type="text" placeholder="Start Date" autocomplete="off">
            </div>
            <div class="builder-field">
                <label for="edu-end-${n}">End Date</label>
                <input id="edu-end-${n}" class="ats-edu-end" type="text" placeholder="End Date" autocomplete="off">
            </div>
            <div class="builder-field">
                <label for="edu-grade-${n}">GPA / Percentage</label>
                <input id="edu-grade-${n}" class="ats-grade" type="text" placeholder="GPA / Percentage" autocomplete="off">
            </div>
        </div>
    `;
    container.appendChild(wrapper);
}

/* ---------------------------------------------------------
   PROJECTS
--------------------------------------------------------- */

function addATSProject() {
    atsProjectCount++;
    const container = document.getElementById("ats-projects-list");
    if (!container) return;
    const n = atsProjectCount;
    const wrapper = document.createElement("div");
    wrapper.className = "builder-repeat-card";
    wrapper.innerHTML = `
        <div class="repeat-card-header">
            <strong>Project ${n}</strong>
            <button type="button" class="remove-button" onclick="this.parentElement.parentElement.remove()">Remove</button>
        </div>
        <div class="builder-field">
            <label for="proj-name-${n}">Project Name</label>
            <input id="proj-name-${n}" class="ats-project-name" type="text" placeholder="Project Name" autocomplete="off">
        </div>
        <div class="builder-field">
            <label for="proj-desc-${n}">Description</label>
            <textarea id="proj-desc-${n}" class="ats-project-description" rows="4" placeholder="Project description" autocomplete="off"></textarea>
        </div>
        <div class="builder-field">
            <label for="proj-tech-${n}">Technologies</label>
            <input id="proj-tech-${n}" class="ats-project-technologies" type="text" placeholder="Technologies (comma separated)" autocomplete="off">
        </div>
    `;
    container.appendChild(wrapper);
}

/* ---------------------------------------------------------
   CERTIFICATIONS
--------------------------------------------------------- */

function addATSCertification() {
    atsCertificationCount++;
    const container = document.getElementById("ats-certifications-list");
    if (!container) return;
    const uid = `ats-cert-${atsCertificationCount}`;
    const wrapper = document.createElement("div");
    wrapper.className = "builder-list-item";
    wrapper.innerHTML = `
        <label for="${uid}" class="visually-hidden">Certification</label>
        <input id="${uid}" type="text" class="ats-certification" placeholder="Certification" autocomplete="off">
        <button type="button" class="remove-builder-item" aria-label="Remove certification" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(wrapper);
}

/* ---------------------------------------------------------
   ACHIEVEMENTS
--------------------------------------------------------- */

function addATSAchievement() {
    atsAchievementCount++;
    const container = document.getElementById("ats-achievements-list");
    if (!container) return;
    const uid = `ats-achv-${atsAchievementCount}`;
    const wrapper = document.createElement("div");
    wrapper.className = "builder-list-item";
    wrapper.innerHTML = `
        <label for="${uid}" class="visually-hidden">Achievement</label>
        <input id="${uid}" type="text" class="ats-achievement" placeholder="Achievement" autocomplete="off">
        <button type="button" class="remove-builder-item" aria-label="Remove achievement" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(wrapper);
}

/* ---------------------------------------------------------
   COLLECT DATA — ids here now match templates/index.html
--------------------------------------------------------- */

function collectATSResumeData() {
    const getValue = (id) => {
        const element = document.getElementById(id);
        return element ? element.value.trim() : "";
    };

    const skills = [...document.querySelectorAll(".ats-skill")]
        .map(el => el.value.trim())
        .filter(Boolean);

    const experience = [...document.querySelectorAll("#ats-experience-list .builder-repeat-card")]
        .map(card => ({
            job_title: card.querySelector(".ats-job-title")?.value.trim() || "",
            company: card.querySelector(".ats-company")?.value.trim() || "",
            location: card.querySelector(".ats-exp-location")?.value.trim() || "",
            start_date: card.querySelector(".ats-start-date")?.value.trim() || "",
            end_date: card.querySelector(".ats-end-date")?.value.trim() || "",
            description: card.querySelector(".ats-exp-description")?.value.trim() || "",
        }));

    const education = [...document.querySelectorAll("#ats-education-list .builder-repeat-card")]
        .map(card => ({
            degree: card.querySelector(".ats-degree")?.value.trim() || "",
            institution: card.querySelector(".ats-institution")?.value.trim() || "",
            location: card.querySelector(".ats-edu-location")?.value.trim() || "",
            start_date: card.querySelector(".ats-edu-start")?.value.trim() || "",
            end_date: card.querySelector(".ats-edu-end")?.value.trim() || "",
            grade: card.querySelector(".ats-grade")?.value.trim() || "",
        }));

    const projects = [...document.querySelectorAll("#ats-projects-list .builder-repeat-card")]
        .map(card => ({
            name: card.querySelector(".ats-project-name")?.value.trim() || "",
            description: card.querySelector(".ats-project-description")?.value.trim() || "",
            technologies: (card.querySelector(".ats-project-technologies")?.value || "")
                .split(",").map(v => v.trim()).filter(Boolean),
        }));

    const certifications = [...document.querySelectorAll(".ats-certification")]
        .map(el => el.value.trim())
        .filter(Boolean);

    const achievements = [...document.querySelectorAll(".ats-achievement")]
        .map(el => el.value.trim())
        .filter(Boolean);

    const languageField = document.getElementById("ats-languages");
    const languages = languageField?.multiple
        ? [...languageField.selectedOptions].map(option => option.value.trim()).filter(Boolean)
        : [...(languageField?.querySelectorAll("input[type='checkbox']:checked") || [])].map(input => input.value.trim()).filter(Boolean);

    return {
        personal: {
            name: getValue("ats-name"),
            title: "",
            email: getValue("ats-email"),
            phone: getValue("ats-phone"),
            location: getValue("ats-location"),
            linkedin: getValue("ats-linkedin"),
            github: "",
            portfolio: getValue("ats-website"),
        },
        summary: getValue("ats-summary"),
        skills,
        experience,
        education,
        projects,
        certifications,
        achievements,
        languages,
    };
}

/* ---------------------------------------------------------
   PREVIEW / ATS CHECK
--------------------------------------------------------- */

async function previewATSResume() {
    const resume = collectATSResumeData();
    if (!resume.personal.name) {
        alert("Please enter your full name.");
        return;
    }

    const jobDescription = document.getElementById("ats-job-description")?.value.trim() || "";

    try {
        const response = await fetch("/preview-ats-resume", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ resume, job_description: jobDescription }),
        });
        const result = await response.json();
        if (!result.success) {
            alert(result.error || "Could not generate preview.");
            return;
        }
        atsPreviewSignature = atsResumeSignature(resume);
        setATSDownloadState(true);
        displayATSResult(result);
    } catch (error) {
        console.error(error);
        alert("Unable to connect to the server.");
    }
}

/* ---------------------------------------------------------
   DISPLAY ATS RESULT
--------------------------------------------------------- */

function displayATSResult(result) {
    const scorePanel = document.getElementById("atsScorePanel");
    const scoreValue = document.getElementById("atsScoreValue");
    const scoreMessage = document.getElementById("atsScoreMessage");

    if (scorePanel) { scorePanel.hidden = false; scorePanel.style.display = "flex"; }

    const score = result.ats?.score || 0;
    if (scoreValue) scoreValue.textContent = score;

    if (scoreMessage) {
        if (score >= 85) scoreMessage.textContent = "Strong ATS-friendly structure.";
        else if (score >= 70) scoreMessage.textContent = "Good structure with some areas to improve.";
        else scoreMessage.textContent = "Several resume sections should be improved.";
    }

    const recommendationList = document.getElementById("atsRecommendationsList");
    if (recommendationList) {
        recommendationList.innerHTML = "";
        (result.ats?.recommendations || []).forEach(rec => {
            const li = document.createElement("li");
            li.textContent = rec;
            recommendationList.appendChild(li);
        });
    }

    const previewContent = document.getElementById("atsResumePreviewContent");
    if (previewContent) {
        previewContent.textContent = result.resume_text || "No resume content could be previewed.";
        previewContent.parentElement?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
}

/* ---------------------------------------------------------
   DOWNLOAD
--------------------------------------------------------- */

async function downloadATSResume(format) {
    const resume = collectATSResumeData();
    if (!resume.personal.name) {
        alert("Please enter your full name.");
        return;
    }
    if (atsPreviewSignature !== atsResumeSignature(resume)) {
        alert("Preview the resume again before downloading so you can review the latest changes.");
        return;
    }

    try {
        const response = await fetch("/download-ats-resume", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ resume, format }),
        });

        if (!response.ok) {
            const error = await response.json();
            alert(error.error || "Could not generate the resume.");
            return;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        const extension = format === "pdf" ? "pdf" : "docx";
        const safeName = resume.personal.name.replace(/[^a-zA-Z0-9_-]+/g, "_").replace(/^_+|_+$/g, "");
        link.download = `${safeName || "ATS_Resume"}_ATS_Resume.${extension}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error(error);
        alert("Unable to download the resume.");
    }
}

// Bind the "Create Resume" button (and modal close controls) as soon as the page loads.
bindATSBuilderActions();
/**
 * script.js – Lab Report Intelligence Agent Frontend Logic
 * =========================================================
 * Architecture Role: UI Layer – Vanilla JS Controller
 * Responsibilities:
 *   - Handle file upload and drag-and-drop
 *   - Call backend API endpoints: /upload, /analyze, /ask
 *   - Render extracted table, risk gauge, patterns, AI summary
 *   - Drive interactive Q&A chat interface
 */

"use strict";

// ============================================================
// CONFIG – change BASE_URL if backend runs on a different port
// ============================================================
const API_BASE = window.location.origin.includes("localhost") ? "" : "http://localhost:8000";

// ============================================================
// STATE
// ============================================================
let uploadedTests = [];      // Raw extracted tests from /upload
let historicalTests = [];    // Raw extracted tests from previous report
let analysisResults = null;  // Full analysis from /analyze
let reportContext = "";      // Text summary of report for Q&A

// ============================================================
// DOM REFERENCES
// ============================================================
const uploadZone = document.getElementById("upload-zone");
const fileInput = document.getElementById("file-input");
const uploadFilename = document.getElementById("upload-filename");
const filenameText = document.getElementById("filename-text");
const btnUpload = document.getElementById("btn-upload");
const uploadLoader = document.getElementById("upload-loader");

const uploadZoneHistorical = document.getElementById("upload-zone-historical");
const fileInputHistorical = document.getElementById("file-input-historical");
const uploadFilenameHistorical = document.getElementById("upload-filename-historical");
const filenameTextHistorical = document.getElementById("filename-text-historical");

const sectionTable = document.getElementById("section-table");
const resultsTbody = document.getElementById("results-tbody");
const testCountBadge = document.getElementById("test-count-badge");
const btnAnalyze = document.getElementById("btn-analyze");
const analyzeLoader = document.getElementById("analyze-loader");

const sectionRisk = document.getElementById("section-risk");
const riskCatBadge = document.getElementById("risk-category-badge");
const gaugeFill = document.getElementById("gauge-fill");
const gaugeEl = document.querySelector(".gauge-track");
const riskScoreText = document.getElementById("risk-score-text");
const statTotal = document.getElementById("stat-total");
const statAbnormal = document.getElementById("stat-abnormal");
const patternsSection = document.getElementById("patterns-section");
const patternsList = document.getElementById("patterns-list");
const trendsSection = document.getElementById("trends-section");
const trendsList = document.getElementById("trends-list");
const emergencyAlert = document.getElementById("emergency-alert");

const sectionSummary = document.getElementById("section-summary");
const aiSummaryText = document.getElementById("ai-summary-text");

const sectionChat = document.getElementById("section-chat");
const chatWindow = document.getElementById("chat-window");
const chatInput = document.getElementById("chat-input");
const btnSend = document.getElementById("btn-send");

// ============================================================
// SECTION 1: FILE UPLOAD
// ============================================================

// Drag-and-drop support
uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("drag-over");
});

uploadZone.addEventListener("dragleave", () => {
    uploadZone.classList.remove("drag-over");
});

uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelected(file);
});

// Keyboard accessibility for upload zone
uploadZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") fileInput.click();
});

fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) handleFileSelected(fileInput.files[0]);
});

function handleFileSelected(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
        showToast("⚠️ Please upload a PDF file.", "warning");
        return;
    }
    filenameText.textContent = file.name;
    uploadFilename.classList.remove("hidden");
    btnUpload.disabled = false;
}

btnUpload.addEventListener("click", async () => {
    const file = fileInput.files[0];
    if (!file) return;

    setLoading(btnUpload, uploadLoader, true);

    // Clear previous results
    sectionTable.classList.add("hidden");
    sectionRisk.classList.add("hidden");
    sectionSummary.classList.add("hidden");
    sectionChat.classList.add("hidden");
    chatWindow.innerHTML = `<div class="chat-welcome"><div class="welcome-icon">🩺</div><p>Ask me anything about your lab report. I'll explain it in simple, calm language.</p></div>`;
    analysisResults = null;
    reportContext = "";

    try {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch(`${API_BASE}/upload`, {
            method: "POST",
            body: formData,
        });

        const data = await handleResponse(res);

        if (!data.tests || data.tests.length === 0) {
            showToast(
                "No lab values could be extracted. The PDF may use an unsupported format.",
                "warning"
            );
            return;
        }

        uploadedTests = data.tests;
        renderResultsTable(uploadedTests);

        // Upload Historical Report if selected
        const fileHist = fileInputHistorical.files[0];
        if (fileHist) {
            const formDataHist = new FormData();
            formDataHist.append("file", fileHist);
            const resHist = await fetch(`${API_BASE}/upload`, {
                method: "POST",
                body: formDataHist,
            });
            const dataHist = await handleResponse(resHist);
            if (dataHist.tests && dataHist.tests.length > 0) {
                historicalTests = dataHist.tests;
                showToast(`✅ Extracted ${dataHist.count} historical test(s) successfully.`, "success");
            }
        }

        sectionTable.classList.remove("hidden");
        sectionTable.scrollIntoView({ behavior: "smooth", block: "start" });
        showToast(`✅ Extracted ${data.count} lab test(s) successfully.`, "success");
    } catch (err) {
        showToast(`❌ Upload failed: ${err.message}`, "error");
    } finally {
        setLoading(btnUpload, uploadLoader, false);
    }
});

// Secondary Upload Drag and Drop
uploadZoneHistorical.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZoneHistorical.classList.add("drag-over");
});

uploadZoneHistorical.addEventListener("dragleave", () => {
    uploadZoneHistorical.classList.remove("drag-over");
});

uploadZoneHistorical.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZoneHistorical.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelectedHistorical(file);
});

uploadZoneHistorical.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") fileInputHistorical.click();
});

fileInputHistorical.addEventListener("change", () => {
    if (fileInputHistorical.files[0]) handleFileSelectedHistorical(fileInputHistorical.files[0]);
});

function handleFileSelectedHistorical(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
        showToast("⚠️ Please upload a PDF file.", "warning");
        return;
    }
    filenameTextHistorical.textContent = file.name;
    uploadFilenameHistorical.classList.remove("hidden");
}

// ============================================================
// SECTION 2: RENDER EXTRACTED TABLE
// ============================================================

function renderResultsTable(tests) {
    resultsTbody.innerHTML = "";
    testCountBadge.textContent = `${tests.length} tests`;

    tests.forEach((t) => {
        const tr = document.createElement("tr");
        tr.dataset.name = t.test_name;

        tr.innerHTML = `
          <td>${escHtml(t.test_name)}</td>
          <td>${escHtml(String(t.measured_value))}</td>
          <td>${escHtml(t.unit || "—")}</td>
          <td>${escHtml(t.reference_range || "—")}</td>
          <td class="status-cell">
            <span class="result-status ${escHtml(t.status || 'Unknown')}">${escHtml(t.status || 'Unknown')}</span>
          </td>
        `;
        resultsTbody.appendChild(tr);
    });
}

function updateTableWithStatus(results) {
    const rows = resultsTbody.querySelectorAll("tr");
    results.forEach((r, i) => {
        const row = Array.from(rows).find(c => c.dataset.name === r.test_name);
        if (row) {
            const statusCell = row.querySelector(".status-cell");

            let statusHtml = `<span class="result-status ${r.status}">${r.status}</span>`;

            if (r.is_critical) {
                row.classList.add("critical");
                statusHtml = `<span class="result-status ${r.status}">${r.status} <i class="fa-solid fa-triangle-exclamation" style="margin-left:4px"></i></span>`;
            }

            if (r.status !== "Normal") {
                const desc = r.status_description || r.description || '';
                statusHtml += `<div class="result-desc">${desc}</div>`;
            }

            statusCell.innerHTML = statusHtml;
        }
    });
}

// ============================================================
// SECTION 3+4+5: ANALYZE REPORT
// ============================================================

btnAnalyze.addEventListener("click", async () => {
    if (!uploadedTests.length) return;

    setLoading(btnAnalyze, analyzeLoader, true);

    try {
        const payload = { tests: uploadedTests };
        if (historicalTests.length > 0) {
            payload.historicalTests = historicalTests;
            payload.historical_tests = historicalTests; // ensure snake_case matches backend
        }

        const res = await fetch(`${API_BASE}/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        const data = await handleResponse(res);
        analysisResults = data;

        // Update cards status cells
        updateTableWithStatus(data.results);

        // Build report context for Q&A
        reportContext = buildReportContext(data);

        // Risk gauge
        renderRiskGauge(data.risk_score, data.risk_category, data.abnormal_count, data.total_count);
        sectionRisk.classList.remove("hidden");

        // Patterns
        if (data.patterns && data.patterns.length > 0) {
            renderPatterns(data.patterns);
            patternsSection.classList.remove("hidden");
        } else {
            patternsSection.classList.add("hidden");
        }

        // Trends
        if (data.trends && data.trends.length > 0) {
            renderTrends(data.trends);
            trendsSection.classList.remove("hidden");
        } else {
            trendsSection.classList.add("hidden");
        }

        // Emergency Alert Detection
        if (data.ai_summary && data.ai_summary.includes("immediate medical attention")) {
            emergencyAlert.classList.remove("hidden");
        } else {
            emergencyAlert.classList.add("hidden");
        }

        // AI summary
        renderSummary(data.ai_summary);
        sectionSummary.classList.remove("hidden");

        // Show chat
        sectionChat.classList.remove("hidden");

        // Scroll to risk section
        sectionRisk.scrollIntoView({ behavior: "smooth", block: "start" });
        showToast("✅ Analysis complete!", "success");
    } catch (err) {
        showToast(`❌ Analysis failed: ${err.message}`, "error");
    } finally {
        setLoading(btnAnalyze, analyzeLoader, false);
    }
});

// ============================================================
// RISK GAUGE RENDERING
// ============================================================

const RISK_CONFIG = {
    Stable: { pct: 10, color: "#2FB344", textColor: "#166534", bg: "#DCFCE7" },
    Monitor: { pct: 35, color: "#F6C343", textColor: "#92400E", bg: "#FFFBEB" },
    "Moderate Concern": { pct: 65, color: "#F97316", textColor: "#7C2D12", bg: "#FFF7ED" },
    "Elevated Risk": { pct: 92, color: "#E55353", textColor: "#991B1B", bg: "#FEE2E2" },
};

function renderRiskGauge(score, category, abnormal, total) {
    const cfg = RISK_CONFIG[category] || RISK_CONFIG["Stable"];

    riskCatBadge.textContent = category;
    riskCatBadge.style.background = cfg.bg;
    riskCatBadge.style.color = cfg.textColor;

    gaugeFill.style.width = cfg.pct + "%";
    gaugeFill.style.background = cfg.color;

    if (gaugeEl) {
        gaugeEl.setAttribute("aria-valuenow", cfg.pct);
    }

    riskScoreText.textContent = score.toFixed(1);
    statTotal.textContent = total;
    statAbnormal.textContent = abnormal;
}

function renderPatterns(patterns) {
    patternsList.innerHTML = "";
    patterns.forEach((p) => {
        const div = document.createElement("div");
        div.className = "pattern-item";
        div.textContent = p.message;
        patternsList.appendChild(div);
    });
}

function renderTrends(trends) {
    trendsList.innerHTML = "";
    trends.forEach((t) => {
        const div = document.createElement("div");
        div.className = "pattern-item";
        const icon = t.percent_change > 0 ? "↗️" : t.percent_change < 0 ? "↘️" : "➡️";
        div.innerHTML = `<strong>${escHtml(t.test_name)}</strong>: ${icon} ${escHtml(t.trend_type)} (${t.percent_change > 0 ? '+' : ''}${t.percent_change}%) <br> <small style="color: #64748b;">Previous: ${t.historical_value} ${t.unit} → Current: ${t.current_value} ${t.unit}</small>`;
        trendsList.appendChild(div);
    });
}

function renderSummary(text) {
    aiSummaryText.innerHTML = markdownToHtml(text || "No summary generated.");
}

// ============================================================
// SECTION 6: Q&A CHAT
// ============================================================

// Suggestion chip click
document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
        chatInput.value = chip.dataset.q;
        chatInput.focus();
    });
});

btnSend.addEventListener("click", sendQuestion);

chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendQuestion();
    }
});

async function sendQuestion() {
    const question = chatInput.value.trim();
    if (!question) return;

    chatInput.value = "";
    btnSend.disabled = true;

    // Remove welcome message on first real message
    const welcome = chatWindow.querySelector(".chat-welcome");
    if (welcome) welcome.remove();

    // Add user bubble
    appendChatBubble(question, "user");

    // Add thinking indicator
    const thinkingEl = appendChatBubble("Thinking…", "thinking");

    try {
        const res = await fetch(`${API_BASE}/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question, report_context: reportContext }),
        });

        const data = await handleResponse(res);
        thinkingEl.remove();

        if (data.success && data.answer) {
            appendChatBubble(data.answer, "bot");
        } else {
            console.error("Chat Error: Invalid response data", data);
            appendChatBubble("I'm sorry, I received an invalid response from the medical agent.", "bot");
        }
    } catch (err) {
        console.error("Chat Fetch Failure:", err);
        thinkingEl.remove();
        appendChatBubble(`Sorry, I couldn't get an answer right now: ${err.message}`, "bot");
    } finally {
        btnSend.disabled = false;
        chatInput.focus();
    }
}

function appendChatBubble(text, type) {
    const div = document.createElement("div");
    div.className = `chat-bubble chat-bubble-${type === "user" ? "user" : type === "thinking" ? "thinking" : "bot"
        }`;
    if (type === "bot") {
        try {
            div.innerHTML = markdownToHtml(text);
        } catch (err) {
            console.error("Markdown Parsing Error:", err);
            div.textContent = text; // Fallback to raw text if parser fails
        }
    } else {
        div.textContent = text;
    }
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
    return div;
}

// ============================================================
// HELPERS
// ============================================================

function setLoading(btn, loader, isLoading) {
    btn.disabled = isLoading;
    loader.classList.toggle("hidden", !isLoading);
}

async function handleResponse(res) {
    if (!res.ok) {
        let msg = `Server error: ${res.status}`;
        try {
            const err = await res.json();
            msg = err.detail || msg;
        } catch (_) { }
        throw new Error(msg);
    }
    try {
        return await res.json();
    } catch (err) {
        throw new Error("Invalid response format from server.");
    }
}

function statusBadge(status, is_critical = false) {
    const classMap = {
        Normal: "status-normal",
        Low: "status-low",
        High: "status-high",
        Unknown: "status-unknown",
        "—": "status-unknown",
    };
    const cls = classMap[status] || "status-unknown";
    let badge = `<span class="status-badge ${cls}">${escHtml(status)}</span>`;
    if (is_critical) {
        badge += ` <span class="status-badge" style="background:#dc2626;color:white;font-weight:bold;margin-left:8px;">🚨 CRITICAL</span>`;
    }
    return badge;
}

function escHtml(str) {
    if (str === null || str === undefined) return "—";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

/**
 * Simple markdown-to-HTML converter for AI output.
 * Supports: **bold**, *italic*, ## headings, - bullets, ---, and line breaks.
 */
function markdownToHtml(md) {
    if (!md) return "";
    // Escape HTML first
    let html = md
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Headings (## Heading)
    html = html.replace(/^##\s+(.+)$/gm, '<strong style="font-size:1.05em;display:block;margin:10px 0 4px">$1</strong>');

    // Horizontal rule (---)
    html = html.replace(/^---$/gm, '<hr>');

    // Bold (**text**)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Italic (*text*) - Using a safer pattern to avoid lookbehind issues in some browsers
    html = html.replace(/([^\*]|^)\*([^\*]+)\*([^\*]|$)/g, '$1<em>$2</em>$3');

    // Bullet points (- item or • item)
    html = html.replace(/^[\-•]\s+(.+)$/gm, '<div style="padding-left:16px;margin:3px 0">• $1</div>');

    // Convert double newlines to paragraph breaks
    html = html.replace(/\n\n/g, '<br><br>');

    // Convert remaining single newlines to breaks
    html = html.replace(/\n/g, '<br>');

    // Add a simple safety card styling if the disclaimer is found
    // Using [\s\S] instead of 's' flag for better compatibility
    html = html.replace(/⚠️([\s\S]*?)\*(.*?)\*/gi, (match, p1, p2) => {
        return `<div class="safety-card"><strong>⚠️ Note:</strong> ${p2}</div>`;
    });

    return html;
}

function buildReportContext(data) {
    const lines = [
        `Risk Category: ${data.risk_category} (Score: ${data.risk_score})`,
        `Tests Outside Reference Range: ${data.abnormal_count} of ${data.total_count}`,
        "",
        "Test Results:",
    ];
    (data.results || []).forEach((r) => {
        lines.push(
            `  ${r.test_name}: ${r.measured_value} ${r.unit} [Ref: ${r.reference_range}] → ${r.status}`
        );
    });
    return lines.join("\n");
}

function showToast(message, type = "info") {
    // Remove any existing toast
    const existing = document.querySelector(".toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;

    const colorMap = {
        success: "#2FB344",
        warning: "#F6C343",
        error: "#E55353",
        info: "#2C7BE5",
    };

    Object.assign(toast.style, {
        position: "fixed",
        bottom: "28px",
        right: "28px",
        background: colorMap[type] || colorMap.info,
        color: "#fff",
        padding: "12px 22px",
        borderRadius: "12px",
        fontSize: "0.88rem",
        fontFamily: "'Inter', sans-serif",
        fontWeight: "600",
        boxShadow: "0 4px 18px rgba(0,0,0,0.18)",
        zIndex: "9999",
        maxWidth: "360px",
        lineHeight: "1.5",
        opacity: "0",
        transition: "opacity 0.25s ease",
    });

    document.body.appendChild(toast);
    requestAnimationFrame(() => { toast.style.opacity = "1"; });

    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

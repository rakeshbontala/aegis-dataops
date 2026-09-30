const INCIDENT_ID = "INC-20260930-001";

async function loadIncident() {
    const timeline = document.getElementById("timeline");

    try {
        const response = await fetch(`/api/incidents/${INCIDENT_ID}`);

        if (!response.ok) {
            throw new Error(`API returned ${response.status}`);
        }

        const incident = await response.json();

        document.getElementById("incident-id").textContent =
            incident.incident_id;

        document.getElementById("pipeline-name").textContent =
            incident.pipeline_name;

        document.getElementById("severity").textContent =
            incident.severity;

        document.getElementById("status").textContent =
            incident.status;

        document.getElementById("error-type").textContent =
            incident.error_type;

        const unexpectedColumn =
            incident.evidence?.[0]?.unexpected_columns?.join(", ") || "None";

        document.getElementById("unexpected-column").textContent =
            unexpectedColumn;

        document.getElementById("strategy").textContent =
            incident.resolution_strategy?.strategy_name || "Not selected";

        document.getElementById("execution-scope").textContent =
            incident.resolution_strategy?.execution_scope || "Unknown";

        document.getElementById("root-cause").textContent =
            incident.root_cause || "No root cause recorded.";

        document.getElementById("production-modified").textContent =
            incident.resolution_strategy?.production_modified
                ? "MODIFIED"
                : "NOT MODIFIED";

        renderAssets(incident.affected_assets || []);
        renderVerification(incident.verification || {});
        renderTimeline(incident.lifecycle || []);

        await loadRiskEvaluation();
        await loadDecision();
        await loadExplanation();
        await loadBlastRadiusAndPrevention();
        await loadAuditTrail();

    } catch (error) {
        timeline.innerHTML = `
            <div class="error">
                Failed to load incident:
                ${escapeHtml(error.message)}
            </div>
        `;
    }
}


async function loadRiskEvaluation() {
    const summary = document.getElementById("risk-summary");
    const container = document.getElementById("risk-evaluations");

    try {
        const response = await fetch(
            `/api/incidents/${INCIDENT_ID}/risk`
        );

        if (!response.ok) {
            throw new Error(`Risk API returned ${response.status}`);
        }

        const riskData = await response.json();

        const evaluations = riskData.risk_evaluations || [];

        summary.textContent =
            `${riskData.evaluated_strategy_count} recovery strategies evaluated.`;

        if (!evaluations.length) {
            container.innerHTML = `
                <div class="loading">
                    No risk evaluations available.
                </div>
            `;
            return;
        }

        container.innerHTML = evaluations.map(evaluation => `
            <div class="risk-card">

                <div class="risk-card-header">
                    <div>
                        <div class="card-label">
                            ${escapeHtml(evaluation.strategy_id)}
                        </div>

                        <h3>
                            ${escapeHtml(evaluation.name)}
                        </h3>
                    </div>

                    <div class="risk-score">
                        <span class="card-label">RISK SCORE</span>
                        <strong>
                            ${escapeHtml(String(evaluation.risk_score))}
                        </strong>
                    </div>
                </div>

                <div class="risk-classification">
                    ${escapeHtml(evaluation.risk_classification)}
                </div>

                <div class="risk-factors">

                    <div>
                        <span class="card-label">EXECUTION</span>
                        <strong>
                            ${escapeHtml(
                                evaluation.risk_factors?.execution_risk || "--"
                            )}
                        </strong>
                    </div>

                    <div>
                        <span class="card-label">RUNTIME</span>
                        <strong>
                            ${escapeHtml(
                                evaluation.risk_factors?.runtime_risk || "--"
                            )}
                        </strong>
                    </div>

                    <div>
                        <span class="card-label">DATA LOSS</span>
                        <strong>
                            ${escapeHtml(
                                evaluation.risk_factors?.data_loss_risk || "--"
                            )}
                        </strong>
                    </div>

                    <div>
                        <span class="card-label">IMPACT SCOPE</span>
                        <strong>
                            ${escapeHtml(
                                String(
                                    evaluation.risk_factors?.impact_scope ?? "--"
                                )
                            )}
                        </strong>
                    </div>

                </div>

                <div class="approval-required">
                    Human approval required
                </div>

            </div>
        `).join("");

    } catch (error) {
        summary.textContent = "Risk evaluation unavailable.";

        container.innerHTML = `
            <div class="error">
                Failed to load risk evaluation:
                ${escapeHtml(error.message)}
            </div>
        `;
    }
}


async function loadDecision() {
    const summary = document.getElementById("decision-summary");

    try {
        const response = await fetch(`/api/incidents/${INCIDENT_ID}/decision`);

        if (!response.ok) {
            throw new Error(`Decision API returned ${response.status}`);
        }

        const decision = await response.json();
        const recommended = decision.recommended_strategy || {};

        document.getElementById("decision-strategy").textContent =
            `${recommended.strategy_id || ""} — ${recommended.name || ""}`;

        document.getElementById("decision-confidence").textContent =
            decision.confidence || "--";

        summary.textContent =
            `AEGIS evaluated ${decision.evaluated_strategies?.length ?? 0} recovery ` +
            `strategies and recommends ${recommended.strategy_id || "--"} ` +
            `(risk score ${recommended.risk_score ?? "--"}, ${recommended.risk_classification || "--"}).`;

        renderList("decision-factors", decision.decision_factors || []);
        renderList("decision-tradeoffs", decision.tradeoffs || []);

        const rejectedContainer = document.getElementById("decision-rejected");
        const rejected = decision.rejected_alternatives || [];

        rejectedContainer.innerHTML = rejected.length
            ? rejected.map(alt => `
                <div class="rejected-card">
                    <strong>${escapeHtml(alt.strategy_id)} — ${escapeHtml(alt.name)}</strong>
                    <ul>
                        ${(alt.reasons || []).map(reason => `<li>${escapeHtml(reason)}</li>`).join("")}
                    </ul>
                </div>
            `).join("")
            : "<div class='loading'>No alternatives were rejected.</div>";

    } catch (error) {
        summary.textContent = "Recovery decision unavailable.";
    }
}


async function loadExplanation() {
    const narrativeEl = document.getElementById("explanation-narrative");
    const sourceEl = document.getElementById("explanation-source");

    try {
        const response = await fetch(`/api/incidents/${INCIDENT_ID}/explanation`);

        if (!response.ok) {
            throw new Error(`Explanation API returned ${response.status}`);
        }

        const explanation = await response.json();

        narrativeEl.textContent = explanation.narrative;
        sourceEl.textContent = explanation.source === "llm"
            ? `AI-GENERATED (${explanation.model})`
            : "DETERMINISTIC";

    } catch (error) {
        narrativeEl.textContent = "Explanation unavailable.";
        sourceEl.textContent = "--";
    }
}


async function loadBlastRadiusAndPrevention() {
    const summary = document.getElementById("blast-radius-summary");
    const assetsContainer = document.getElementById("blast-radius-assets");
    const preventionContainer = document.getElementById("prevention-controls");

    try {
        const response = await fetch(`/api/incidents/${INCIDENT_ID}/impact`);

        if (!response.ok) {
            throw new Error(`Impact API returned ${response.status}`);
        }

        const impact = await response.json();
        const impactedAssets = impact.impacted_assets || [];

        summary.textContent =
            `${impactedAssets.length} downstream asset(s) affected, starting from ` +
            `${impact.starting_asset || "the source"}.`;

        assetsContainer.innerHTML = impactedAssets.length
            ? impactedAssets.map(asset => `
                <span class="asset">
                    ${escapeHtml(asset.asset)} · ${escapeHtml(asset.criticality || "UNKNOWN")}
                </span>
            `).join("")
            : "<span class='asset'>None</span>";

    } catch (error) {
        summary.textContent = "Blast radius unavailable.";
    }

    try {
        const response = await fetch(`/api/incidents/${INCIDENT_ID}/prevention`);

        if (!response.ok) {
            throw new Error(`Prevention API returned ${response.status}`);
        }

        const prevention = await response.json();
        const controls = prevention.prevention_controls || [];

        preventionContainer.innerHTML = controls.length
            ? controls.map(control => `
                <div class="prevention-item">
                    <strong>${escapeHtml(control.name)}</strong>
                    <span>${escapeHtml(control.description)}</span>
                </div>
            `).join("")
            : "<div class='loading'>No prevention recommendations yet.</div>";

    } catch (error) {
        preventionContainer.innerHTML = `
            <div class="error">Prevention recommendations unavailable.</div>
        `;
    }
}


async function loadAuditTrail() {
    const container = document.getElementById("audit-timeline");

    try {
        const response = await fetch(`/api/incidents/${INCIDENT_ID}/audit`);

        if (!response.ok) {
            throw new Error(`Audit API returned ${response.status}`);
        }

        const audit = await response.json();
        const events = audit.events || [];

        updateApprovalStatus(events);

        if (!events.length) {
            container.innerHTML = "<div class='loading'>No audit events recorded yet.</div>";
            return;
        }

        container.innerHTML = events.map(event => `
            <div class="timeline-item">
                <div class="timeline-status">${escapeHtml(event.action)} — ${escapeHtml(event.status)}</div>
                <div class="timeline-description">Actor: ${escapeHtml(event.actor)}</div>
                <div class="timeline-time">${formatTimestamp(event.timestamp)}</div>
            </div>
        `).join("");

    } catch (error) {
        container.innerHTML = `
            <div class="error">Failed to load audit trail: ${escapeHtml(error.message)}</div>
        `;
    }
}


function updateApprovalStatus(events) {
    const approvalField = document.getElementById("decision-approval");
    const relevant = events.filter(
        e => e.action === "approval_granted" || e.action === "approval_rejected"
    );
    const latest = relevant[relevant.length - 1];

    if (!latest) {
        approvalField.textContent = "PENDING";
        approvalField.className = "";
        return;
    }

    if (latest.action === "approval_granted") {
        approvalField.textContent = "APPROVED";
        approvalField.className = "success";
    } else {
        approvalField.textContent = "REJECTED";
        approvalField.className = "error";
    }
}


function renderList(elementId, items) {
    const container = document.getElementById(elementId);

    container.innerHTML = items.length
        ? items.map(item => `<li>${escapeHtml(item)}</li>`).join("")
        : "<li>No data available.</li>";
}


function renderAssets(assets) {
    const container = document.getElementById("affected-assets");

    if (!assets.length) {
        container.innerHTML = "<span class='asset'>None</span>";
        return;
    }

    container.innerHTML = assets
        .map(asset => `
            <span class="asset">
                ${escapeHtml(asset)}
            </span>
        `)
        .join("");
}


function renderVerification(verification) {
    const container = document.getElementById("verification");

    const checks = [
        ["POST-EXECUTION", verification.post_execution_status],
        ["DATA VERIFICATION", verification.data_verification_status],
        ["SCHEMA MATCH", verification.schema_match ? "PASSED" : "FAILED"],
        ["ROW COUNT MATCH", verification.row_count_match ? "PASSED" : "FAILED"],
        ["BUSINESS VALUES", verification.business_values_match ? "PASSED" : "FAILED"],
        ["ADDED RECORDS", verification.added_records ?? 0],
        ["REMOVED RECORDS", verification.removed_records ?? 0]
    ];

    container.innerHTML = checks.map(([label, value]) => `
        <div class="verification-item">
            <span class="card-label">
                ${escapeHtml(label)}
            </span>

            <strong>
                ${escapeHtml(String(value))}
            </strong>
        </div>
    `).join("");
}


function renderTimeline(lifecycle) {
    const container = document.getElementById("timeline");

    if (!lifecycle.length) {
        container.innerHTML = `
            <div class="loading">
                No lifecycle events recorded.
            </div>
        `;
        return;
    }

    container.innerHTML = lifecycle.map(event => `
        <div class="timeline-item">

            <div class="timeline-status">
                ${escapeHtml(event.status)}
            </div>

            <div class="timeline-description">
                ${escapeHtml(event.description)}
            </div>

            <div class="timeline-time">
                ${formatTimestamp(event.timestamp)}
            </div>

        </div>
    `).join("");
}


function formatTimestamp(timestamp) {
    if (!timestamp) {
        return "Unknown time";
    }

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return timestamp;
    }

    return date.toLocaleString();
}


function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


loadIncident();
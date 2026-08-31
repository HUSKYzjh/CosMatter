-- CosMatter evidence-maturity registry: relational storage template.
--
-- This schema stores only bounded claim text, stable identifiers, audit status,
-- and review states. Never store PDF bytes, unrestricted quotations, URLs,
-- cookies, credentials, local paths, or raw provider payloads in these tables.
--
-- SQLite: execute `PRAGMA foreign_keys = ON` for each connection.
-- PostgreSQL: TEXT, INTEGER, CHECK, UNIQUE, and FOREIGN KEY below are portable.
-- The application validator remains authoritative for cross-row rules, including
-- independent-run separation and the data-support/reproduction promotion gates.

CREATE TABLE evidence_maturity_registry (
    registry_id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    schema_version TEXT NOT NULL CHECK (schema_version = 'cosmatter.evidence-maturity-registry/v1'),
    trust_status TEXT NOT NULL CHECK (trust_status IN (
        'blank_human_evidence_maturity_registry_template_not_evidence',
        'delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence',
        'human_reviewed_evidence_maturity_registry_not_scientific_conclusion'
    )),
    registry_sha256 TEXT NOT NULL UNIQUE CHECK (length(registry_sha256) = 64),
    recorded_at TEXT NOT NULL,
    CHECK (length(trim(registry_id)) BETWEEN 1 AND 120),
    CHECK (length(trim(question_id)) BETWEEN 1 AND 120)
);

CREATE TABLE research_claim (
    registry_id TEXT NOT NULL REFERENCES evidence_maturity_registry(registry_id) ON DELETE CASCADE,
    claim_id TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    maturity_level TEXT NOT NULL CHECK (maturity_level IN (
        'literature_mentioned', 'data_supported', 'reproducibility_ready', 'independently_reproduced'
    )),
    assessment_authority TEXT NOT NULL CHECK (assessment_authority IN (
        'unreviewed', 'delegated_automated_trial', 'human_source_review',
        'human_data_review', 'human_reproducibility_review', 'independent_reproduction_review'
    )),
    PRIMARY KEY (registry_id, claim_id),
    CHECK (length(trim(claim_id)) BETWEEN 1 AND 120),
    CHECK (length(trim(claim_text)) BETWEEN 1 AND 1000),
    CHECK (assessment_authority <> 'delegated_automated_trial' OR maturity_level = 'literature_mentioned')
);

-- Optional metadata-only version registry. DOI is optional and never the sole
-- evidence link; the claim-support table retains the reviewed source-map state.
CREATE TABLE document_version (
    document_id TEXT NOT NULL,
    document_version TEXT NOT NULL CHECK (document_version IN (
        'publisher_version', 'accepted_manuscript', 'preprint', 'unknown',
        'publisher_open_access_mirror_version_not_human_verified'
    )),
    normalized_doi TEXT,
    access_boundary TEXT NOT NULL CHECK (access_boundary IN (
        'metadata_only', 'authorized_local_review', 'institutional_internal_review_only', 'not_recorded'
    )),
    PRIMARY KEY (document_id, document_version),
    CHECK (length(trim(document_id)) BETWEEN 1 AND 200)
);

CREATE TABLE claim_support (
    support_id TEXT PRIMARY KEY,
    registry_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    source_run_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    document_version TEXT NOT NULL,
    independence_group TEXT NOT NULL,
    source_map_status TEXT NOT NULL CHECK (source_map_status IN ('none', 'automated_trial_only', 'human_reviewed')),
    data_status TEXT NOT NULL CHECK (data_status IN ('not_checked', 'narrative_only', 'numeric_or_figure_data_human_checked')),
    conditions_status TEXT NOT NULL CHECK (conditions_status IN ('not_checked', 'partial', 'complete_human_checked')),
    stance TEXT NOT NULL CHECK (stance IN ('supports', 'contradicts', 'mixed', 'boundary_counterexample', 'context_only')),
    FOREIGN KEY (registry_id, claim_id) REFERENCES research_claim(registry_id, claim_id) ON DELETE CASCADE,
    FOREIGN KEY (document_id, document_version) REFERENCES document_version(document_id, document_version),
    CHECK (length(trim(support_id)) BETWEEN 1 AND 120),
    CHECK (length(trim(source_run_id)) BETWEEN 1 AND 120),
    CHECK (length(trim(independence_group)) BETWEEN 1 AND 200)
);

CREATE TABLE reproducibility_assessment (
    registry_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    protocol_status TEXT NOT NULL CHECK (protocol_status IN ('not_checked', 'partial', 'complete_human_checked')),
    materials_status TEXT NOT NULL CHECK (materials_status IN ('not_checked', 'partial', 'complete_human_checked')),
    measurement_status TEXT NOT NULL CHECK (measurement_status IN ('not_checked', 'partial', 'complete_human_checked')),
    raw_data_status TEXT NOT NULL CHECK (raw_data_status IN ('not_checked', 'available', 'not_available', 'not_required')),
    assessment TEXT NOT NULL CHECK (assessment IN ('not_assessed', 'insufficient', 'reproducibility_ready_human_reviewed')),
    PRIMARY KEY (registry_id, claim_id),
    FOREIGN KEY (registry_id, claim_id) REFERENCES research_claim(registry_id, claim_id) ON DELETE CASCADE
);

CREATE TABLE independent_reproduction (
    reproduction_id TEXT PRIMARY KEY,
    registry_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('not_attempted', 'planned', 'in_progress', 'replicated', 'not_replicated', 'inconclusive')),
    independent_run_id TEXT,
    result_comparison TEXT NOT NULL CHECK (result_comparison IN ('not_available', 'within_predefined_tolerance', 'outside_predefined_tolerance', 'inconclusive')),
    review_status TEXT NOT NULL CHECK (review_status IN ('not_reviewed', 'human_reviewed')),
    FOREIGN KEY (registry_id, claim_id) REFERENCES research_claim(registry_id, claim_id) ON DELETE CASCADE,
    CHECK (length(trim(reproduction_id)) BETWEEN 1 AND 120),
    CHECK (independent_run_id IS NULL OR length(trim(independent_run_id)) BETWEEN 1 AND 160),
    CHECK (status <> 'replicated' OR (result_comparison = 'within_predefined_tolerance' AND review_status = 'human_reviewed' AND independent_run_id IS NOT NULL))
);

CREATE TABLE claim_limitation (
    registry_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 1 AND ordinal <= 30),
    limitation_text TEXT NOT NULL,
    PRIMARY KEY (registry_id, claim_id, ordinal),
    FOREIGN KEY (registry_id, claim_id) REFERENCES research_claim(registry_id, claim_id) ON DELETE CASCADE,
    CHECK (length(trim(limitation_text)) BETWEEN 1 AND 500)
);

-- Count-only binding receipt. It is safe to export only when its SHA-256 and
-- counts still match a registry validated by the application layer.
CREATE TABLE evidence_maturity_registry_audit (
    registry_id TEXT PRIMARY KEY REFERENCES evidence_maturity_registry(registry_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    audit_schema_version TEXT NOT NULL CHECK (audit_schema_version = 'cosmatter.evidence-maturity-registry-audit/v2'),
    trust_status TEXT NOT NULL CHECK (trust_status = 'evidence_maturity_registry_link_audit_not_scientific_evidence'),
    registry_sha256 TEXT NOT NULL CHECK (length(registry_sha256) = 64),
    claim_count INTEGER NOT NULL CHECK (claim_count >= 0),
    support_record_count INTEGER NOT NULL CHECK (support_record_count >= 0),
    controlled_source_map_count INTEGER NOT NULL CHECK (controlled_source_map_count >= 0),
    context_only_count INTEGER NOT NULL CHECK (context_only_count >= 0),
    link_error_count INTEGER NOT NULL CHECK (link_error_count >= 0),
    passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
    CHECK (passed = CASE WHEN link_error_count = 0 THEN 1 ELSE 0 END)
);

CREATE INDEX claim_support_claim_idx ON claim_support (registry_id, claim_id);
CREATE INDEX claim_support_document_idx ON claim_support (document_id, document_version);
CREATE INDEX research_claim_maturity_idx ON research_claim (registry_id, maturity_level);

-- CosMatter condition-bound material observation registry.
--
-- This schema stores vocabulary, bounded scalar observations, review state, and
-- exact Source Map bindings.  It must not store PDF bytes, unrestricted quotes,
-- URLs, credentials, local paths, cookies, or provider payloads.
--
-- SQLite callers must enable `PRAGMA foreign_keys = ON` on every connection.
-- Cross-row rules such as exactly twelve qualifier rows and catalog-specific
-- unit membership remain enforced by material_indicator_registry.py.

CREATE TABLE material_indicator_catalog (
    catalog_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL CHECK (schema_version = 'cosmatter.material-indicator-catalog/v1'),
    material_scope TEXT NOT NULL,
    trust_status TEXT NOT NULL CHECK (trust_status = 'curated_indicator_vocabulary_not_scientific_evidence'),
    catalog_sha256 TEXT NOT NULL UNIQUE CHECK (length(catalog_sha256) = 64),
    recorded_at TEXT NOT NULL,
    CHECK (length(trim(catalog_id)) BETWEEN 1 AND 160),
    CHECK (length(trim(material_scope)) BETWEEN 1 AND 120)
);

CREATE TABLE material_indicator_qualifier_definition (
    catalog_id TEXT NOT NULL REFERENCES material_indicator_catalog(catalog_id) ON DELETE CASCADE,
    qualifier_id TEXT NOT NULL CHECK (qualifier_id IN (
        'sample_form', 'composition', 'orientation', 'substrate', 'thickness', 'strain',
        'temperature', 'frequency', 'field_protocol', 'electrode', 'preparation',
        'measurement_geometry'
    )),
    ordinal INTEGER NOT NULL CHECK (ordinal BETWEEN 1 AND 12),
    display_name_zh TEXT NOT NULL,
    description_zh TEXT NOT NULL,
    PRIMARY KEY (catalog_id, qualifier_id),
    UNIQUE (catalog_id, ordinal)
);

CREATE TABLE material_indicator_definition (
    catalog_id TEXT NOT NULL REFERENCES material_indicator_catalog(catalog_id) ON DELETE CASCADE,
    indicator_id TEXT NOT NULL,
    family TEXT NOT NULL CHECK (family IN (
        'structure_phase', 'ferroelectric', 'electrical_transport', 'phase_transition'
    )),
    priority TEXT NOT NULL CHECK (priority = 'P0'),
    category TEXT NOT NULL CHECK (category IN ('structure', 'property', 'experimental_condition')),
    display_name_zh TEXT NOT NULL,
    quantity_kind TEXT NOT NULL,
    canonical_unit TEXT,
    value_shape TEXT NOT NULL CHECK (value_shape IN ('numeric', 'categorical')),
    PRIMARY KEY (catalog_id, indicator_id),
    CHECK (length(trim(indicator_id)) BETWEEN 1 AND 160),
    CHECK (length(trim(display_name_zh)) BETWEEN 1 AND 120)
);

CREATE TABLE material_indicator_allowed_unit (
    catalog_id TEXT NOT NULL,
    indicator_id TEXT NOT NULL,
    unit_key TEXT NOT NULL,
    reported_unit TEXT,
    PRIMARY KEY (catalog_id, indicator_id, unit_key),
    FOREIGN KEY (catalog_id, indicator_id)
        REFERENCES material_indicator_definition(catalog_id, indicator_id) ON DELETE CASCADE,
    CHECK (unit_key = COALESCE(reported_unit, '__unitless__'))
);

CREATE TABLE material_indicator_required_qualifier (
    catalog_id TEXT NOT NULL,
    indicator_id TEXT NOT NULL,
    qualifier_id TEXT NOT NULL,
    PRIMARY KEY (catalog_id, indicator_id, qualifier_id),
    FOREIGN KEY (catalog_id, indicator_id)
        REFERENCES material_indicator_definition(catalog_id, indicator_id) ON DELETE CASCADE,
    FOREIGN KEY (catalog_id, qualifier_id)
        REFERENCES material_indicator_qualifier_definition(catalog_id, qualifier_id) ON DELETE CASCADE
);

CREATE TABLE material_observation_set (
    observation_set_id TEXT PRIMARY KEY,
    catalog_id TEXT NOT NULL REFERENCES material_indicator_catalog(catalog_id),
    material_scope TEXT NOT NULL,
    schema_version TEXT NOT NULL CHECK (schema_version = 'cosmatter.material-observation-set/v1'),
    trust_status TEXT NOT NULL CHECK (trust_status IN (
        'candidate_literature_observations_not_human_data_checked',
        'human_reviewed_material_observations_not_scientific_conclusion'
    )),
    observation_set_sha256 TEXT NOT NULL UNIQUE CHECK (length(observation_set_sha256) = 64),
    recorded_at TEXT NOT NULL,
    UNIQUE (observation_set_id, trust_status),
    CHECK (length(trim(observation_set_id)) BETWEEN 1 AND 160)
);

CREATE TABLE material_observation (
    observation_set_id TEXT NOT NULL,
    set_trust_status TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    catalog_id TEXT NOT NULL,
    indicator_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    normalized_doi TEXT,
    document_version TEXT NOT NULL CHECK (document_version IN (
        'publisher_version', 'accepted_manuscript', 'preprint', 'unknown',
        'publisher_open_access_mirror_version_not_human_verified'
    )),
    category TEXT NOT NULL CHECK (category IN ('structure', 'property', 'experimental_condition')),
    reported_text TEXT,
    reported_value REAL,
    reported_lower REAL,
    reported_upper REAL,
    reported_uncertainty REAL,
    reported_unit TEXT,
    normalized_value REAL,
    normalized_lower REAL,
    normalized_upper REAL,
    normalized_unit TEXT,
    value_semantics TEXT NOT NULL CHECK (value_semantics IN (
        'exact', 'approximate', 'range', 'lower_bound', 'upper_bound',
        'maximum', 'minimum', 'plus_minus', 'categorical'
    )),
    measurement_method TEXT NOT NULL,
    segment_id TEXT,
    locator TEXT,
    source_quote_sha256 TEXT,
    source_map_status TEXT NOT NULL CHECK (source_map_status IN ('none', 'human_reviewed')),
    data_status TEXT NOT NULL CHECK (data_status IN ('not_checked', 'numeric_or_figure_data_human_checked')),
    conditions_status TEXT NOT NULL CHECK (conditions_status IN ('not_checked', 'partial', 'complete_human_checked')),
    maturity_level TEXT NOT NULL CHECK (maturity_level IN (
        'literature_mentioned', 'data_supported', 'reproducibility_ready', 'independently_reproduced'
    )),
    assessment_authority TEXT NOT NULL CHECK (assessment_authority IN (
        'unreviewed', 'human_source_review', 'human_data_review',
        'human_reproducibility_review', 'independent_reproduction_review'
    )),
    limitation TEXT NOT NULL,
    PRIMARY KEY (observation_set_id, observation_id),
    FOREIGN KEY (observation_set_id, set_trust_status)
        REFERENCES material_observation_set(observation_set_id, trust_status) ON DELETE CASCADE,
    FOREIGN KEY (catalog_id, indicator_id)
        REFERENCES material_indicator_definition(catalog_id, indicator_id),
    CHECK (length(trim(observation_id)) BETWEEN 1 AND 160),
    CHECK (length(trim(document_id)) BETWEEN 1 AND 200),
    CHECK (length(trim(measurement_method)) BETWEEN 1 AND 160),
    CHECK (length(trim(limitation)) BETWEEN 1 AND 500),
    CHECK (reported_uncertainty IS NULL OR reported_uncertainty >= 0),
    CHECK (value_semantics <> 'range' OR (reported_lower IS NOT NULL AND reported_upper IS NOT NULL AND reported_lower <= reported_upper)),
    CHECK (value_semantics <> 'plus_minus' OR (reported_value IS NOT NULL AND reported_uncertainty IS NOT NULL)),
    CHECK (value_semantics <> 'categorical' OR (reported_text IS NOT NULL AND reported_value IS NULL)),
    CHECK (
        (source_map_status = 'none' AND segment_id IS NULL AND locator IS NULL AND source_quote_sha256 IS NULL)
        OR
        (source_map_status = 'human_reviewed' AND segment_id IS NOT NULL AND locator IS NOT NULL AND length(source_quote_sha256) = 64)
    ),
    CHECK (
        set_trust_status <> 'candidate_literature_observations_not_human_data_checked'
        OR (
            maturity_level = 'literature_mentioned' AND assessment_authority = 'unreviewed'
            AND source_map_status = 'none' AND data_status = 'not_checked'
            AND conditions_status IN ('not_checked', 'partial')
        )
    ),
    CHECK (
        set_trust_status <> 'human_reviewed_material_observations_not_scientific_conclusion'
        OR assessment_authority <> 'unreviewed'
    ),
    CHECK (
        maturity_level = 'literature_mentioned'
        OR (
            assessment_authority IN ('human_data_review', 'human_reproducibility_review', 'independent_reproduction_review')
            AND source_map_status = 'human_reviewed'
            AND data_status = 'numeric_or_figure_data_human_checked'
            AND conditions_status = 'complete_human_checked'
        )
    )
);

CREATE TABLE material_observation_qualifier (
    observation_set_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    qualifier_id TEXT NOT NULL CHECK (qualifier_id IN (
        'sample_form', 'composition', 'orientation', 'substrate', 'thickness', 'strain',
        'temperature', 'frequency', 'field_protocol', 'electrode', 'preparation',
        'measurement_geometry'
    )),
    qualifier_value TEXT,
    PRIMARY KEY (observation_set_id, observation_id, qualifier_id),
    FOREIGN KEY (observation_set_id, observation_id)
        REFERENCES material_observation(observation_set_id, observation_id) ON DELETE CASCADE,
    CHECK (qualifier_value IS NULL OR length(qualifier_value) <= 500)
);

CREATE INDEX material_observation_indicator_idx
    ON material_observation (catalog_id, indicator_id, maturity_level);
CREATE INDEX material_observation_document_idx
    ON material_observation (document_id, document_version);
CREATE INDEX material_observation_review_idx
    ON material_observation (source_map_status, data_status, conditions_status);

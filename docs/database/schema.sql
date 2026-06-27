-- =============================================================================
-- AI Procurement Agent — PostgreSQL Schema (clean blueprint, CREATE only)
-- Client: Fuyao Europe   |   GenAI Group Project
--
-- Builds the whole database ONCE on a fresh, empty PostgreSQL / Supabase
-- project. No destructive operations (no DROP). If run on a DB that already
-- has these tables it errors with "already exists" and changes nothing.
-- To change a live database, use a small ALTER (migration) instead.
-- =============================================================================

BEGIN;

CREATE TYPE supplier_origin AS ENUM ('internal', 'web');   -- internal = 老系统已有 / web = 网上找到
CREATE TYPE product_kind    AS ENUM ('standard', 'custom');
CREATE TYPE request_status  AS ENUM ('new', 'sourcing', 'quoting', 'ranked', 'exported', 'closed');
CREATE TYPE export_format   AS ENUM ('xlsx', 'pdf', 'csv', 'json');

CREATE TABLE category (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_id   BIGINT REFERENCES category(id) ON DELETE SET NULL,
    name_de     TEXT,
    name_zh     TEXT,
    UNIQUE (parent_id, name_de, name_zh)
);

CREATE TABLE supplier (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    external_id   TEXT UNIQUE,                         -- backend id ("sup-1") or crawler URL
    name          TEXT NOT NULL,
    origin        supplier_origin NOT NULL DEFAULT 'web',
    website       TEXT,
    country       TEXT,
    contact_name  TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    scale         TEXT,
    rating        NUMERIC(3,2),
    attributes    JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, website)
);

CREATE TABLE product (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    external_id         TEXT UNIQUE,
    category_id         BIGINT REFERENCES category(id) ON DELETE SET NULL,
    name_de             TEXT,
    name_zh             TEXT,
    description         TEXT,
    kind                product_kind NOT NULL DEFAULT 'standard',
    model               TEXT,
    article_number      TEXT,
    photo_url           TEXT,
    reference_price     NUMERIC(12,2),
    currency            CHAR(3) NOT NULL DEFAULT 'EUR',
    preferred_supplier  BIGINT REFERENCES supplier(id) ON DELETE SET NULL,
    notes               TEXT,
    attributes          JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE procurement_request (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_text  TEXT,
    requested_by  TEXT,
    status        request_status NOT NULL DEFAULT 'new',
    region_filter TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE request_item (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id  BIGINT NOT NULL REFERENCES procurement_request(id) ON DELETE CASCADE,
    product_id  BIGINT REFERENCES product(id) ON DELETE SET NULL,
    raw_query   TEXT,
    quantity    NUMERIC(12,2),
    unit        TEXT
);

CREATE TABLE quote (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    external_id      TEXT UNIQUE,
    product_id       BIGINT REFERENCES product(id) ON DELETE CASCADE,
    request_item_id  BIGINT REFERENCES request_item(id) ON DELETE SET NULL,
    supplier_id      BIGINT REFERENCES supplier(id) ON DELETE SET NULL,
    listing_title    TEXT,
    price            NUMERIC(12,2),
    currency         CHAR(3) NOT NULL DEFAULT 'EUR',
    lead_time_text   TEXT,
    lead_time_days   INT,
    in_stock         BOOLEAN,
    source_url       TEXT,
    score            NUMERIC(6,3),
    is_selected      BOOLEAN NOT NULL DEFAULT FALSE,
    attributes       JSONB NOT NULL DEFAULT '{}',
    captured_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sourcing_session (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id    BIGINT REFERENCES procurement_request(id) ON DELETE CASCADE,
    need_text     TEXT,
    region_filter TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sourcing_candidate (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id   BIGINT NOT NULL REFERENCES sourcing_session(id) ON DELETE CASCADE,
    supplier_id  BIGINT REFERENCES supplier(id) ON DELETE SET NULL,
    relevance    NUMERIC(6,3),
    quality_note TEXT,
    is_incumbent BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE report (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id  BIGINT REFERENCES procurement_request(id) ON DELETE SET NULL,
    format      export_format NOT NULL,
    file_path   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE feedback (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id  BIGINT REFERENCES procurement_request(id) ON DELETE CASCADE,
    quote_id    BIGINT REFERENCES quote(id) ON DELETE SET NULL,
    approved    BOOLEAN,
    comment     TEXT,
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Frontend memory / conversation history.
-- Stores complete request/result snapshots for reopening past sourcing and comparison runs.
CREATE TABLE conversation_history (
    id               TEXT PRIMARY KEY,
    user_email       TEXT NOT NULL,
    module           TEXT NOT NULL CHECK (module IN ('sourcing', 'comparison')),
    query            TEXT NOT NULL,
    filters          JSONB NOT NULL DEFAULT '{}',
    restore          JSONB,
    request_snapshot JSONB,
    results_snapshot JSONB,
    result_count     INTEGER NOT NULL DEFAULT 0,
    candidate_names  JSONB NOT NULL DEFAULT '[]',
    feedback         JSONB,
    timestamp_ms     BIGINT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- 历史供应商:每次最终采用了哪家供应商买了哪个产品
CREATE TABLE purchase_history (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id   BIGINT REFERENCES product(id) ON DELETE SET NULL,
    supplier_id  BIGINT REFERENCES supplier(id) ON DELETE SET NULL,
    quote_id     BIGINT REFERENCES quote(id) ON DELETE SET NULL,
    request_id   BIGINT REFERENCES procurement_request(id) ON DELETE SET NULL,
    price        NUMERIC(12,2),
    currency     CHAR(3) NOT NULL DEFAULT 'EUR',
    decided_by   TEXT,
    notes        TEXT,
    purchased_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_product_category  ON product(category_id);
CREATE INDEX idx_product_article   ON product(article_number);
CREATE INDEX idx_quote_product     ON quote(product_id);
CREATE INDEX idx_quote_supplier    ON quote(supplier_id);
CREATE INDEX idx_quote_captured    ON quote(captured_at DESC);
CREATE INDEX idx_quote_selected    ON quote(product_id) WHERE is_selected;
CREATE INDEX idx_reqitem_request   ON request_item(request_id);
CREATE INDEX idx_candidate_session ON sourcing_candidate(session_id);
CREATE INDEX idx_purchase_product  ON purchase_history(product_id);
CREATE INDEX idx_purchase_supplier ON purchase_history(supplier_id);
CREATE INDEX idx_conversation_history_user_time ON conversation_history(user_email, timestamp_ms DESC);
CREATE INDEX idx_conversation_history_user_module_time ON conversation_history(user_email, module, timestamp_ms DESC);
CREATE INDEX idx_product_attrs     ON product  USING GIN (attributes);
CREATE INDEX idx_supplier_attrs    ON supplier USING GIN (attributes);

CREATE VIEW v_product_best_quote AS
SELECT DISTINCT ON (q.product_id)
       q.product_id, p.name_de, p.name_zh, s.name AS supplier_name,
       q.price, q.currency, q.lead_time_text, q.source_url, q.captured_at
FROM   quote q
JOIN   product  p ON p.id = q.product_id
LEFT   JOIN supplier s ON s.id = q.supplier_id
ORDER  BY q.product_id, q.is_selected DESC, q.price ASC, q.captured_at DESC;

COMMIT;

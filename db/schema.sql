-- TacSRT Contract Dashboard - Database Schema

CREATE TABLE IF NOT EXISTS job_codes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL UNIQUE,
    bid_rate      REAL    NOT NULL,
    employee_rate REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS imagery_catalog (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    provider          TEXT    NOT NULL,
    description       TEXT    NOT NULL,
    min_area_km2      REAL,
    resolution        TEXT,
    pricing_guidance  TEXT,
    list_price        REAL    NOT NULL,
    sh_price          REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pws_number      TEXT    NOT NULL,
    report_title    TEXT    NOT NULL,
    start_date      TEXT,
    end_date        TEXT,
    status          TEXT    NOT NULL DEFAULT 'Ongoing',
    notes           TEXT,
    days            INTEGER DEFAULT 1,
    is_daily_rate   INTEGER DEFAULT 0,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS labor_entries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id       INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_code_id      INTEGER NOT NULL REFERENCES job_codes(id),
    person_name      TEXT,
    hours            REAL    NOT NULL DEFAULT 0,
    employee_rate    REAL    NOT NULL,
    bid_rate         REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS imagery_orders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id       INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    catalog_id       INTEGER REFERENCES imagery_catalog(id),
    provider         TEXT    NOT NULL,
    product          TEXT    NOT NULL,
    order_date       TEXT,
    order_status     TEXT    NOT NULL DEFAULT 'Requested',
    aoi              TEXT,
    shots_requested  INTEGER DEFAULT 0,
    shots_delivered  INTEGER DEFAULT 0,
    cost_per_shot    REAL    NOT NULL DEFAULT 0,
    charge_per_shot  REAL    NOT NULL DEFAULT 0,
    cost             REAL    NOT NULL DEFAULT 0,
    charge           REAL    NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS day_rate_options (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    total_exercised         INTEGER NOT NULL DEFAULT 0,
    total_used              INTEGER NOT NULL DEFAULT 0,
    additional_options      INTEGER NOT NULL DEFAULT 0,
    updated_at              TEXT    DEFAULT (datetime('now'))
);

-- Per-PWS day rate tracking
CREATE TABLE IF NOT EXISTS pws_day_rate (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    pws_number        TEXT    NOT NULL UNIQUE,
    pws_name          TEXT    NOT NULL DEFAULT '',
    total_exercised   INTEGER NOT NULL DEFAULT 0,
    start_date        TEXT,
    end_date          TEXT,
    updated_at        TEXT    DEFAULT (datetime('now'))
);

-- Revenue streams: Diamond, Athena, Sourced
CREATE TABLE IF NOT EXISTS revenue_streams (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    diamond_money       REAL    NOT NULL DEFAULT 0,
    diamond_weeks       REAL    NOT NULL DEFAULT 0,
    athena_billed       REAL    NOT NULL DEFAULT 0,
    sourced_total       REAL    NOT NULL DEFAULT 0,
    notes               TEXT,
    updated_at          TEXT    DEFAULT (datetime('now'))
);

-- Indices for JOIN performance on foreign keys
CREATE INDEX IF NOT EXISTS idx_labor_project_id   ON labor_entries(project_id);
CREATE INDEX IF NOT EXISTS idx_labor_job_code_id  ON labor_entries(job_code_id);
CREATE INDEX IF NOT EXISTS idx_orders_project_id  ON imagery_orders(project_id);
CREATE INDEX IF NOT EXISTS idx_orders_catalog_id  ON imagery_orders(catalog_id);

-- Views for aggregated profit tracking

DROP VIEW IF EXISTS v_project_profit;
CREATE VIEW v_project_profit AS
SELECT
    p.id AS project_id,
    p.pws_number,
    p.report_title,
    p.status,
    p.days,
    p.start_date,
    p.end_date,
    COALESCE(labor.total_cost, 0)    AS labor_cost,
    COALESCE(labor.total_charge, 0)  AS labor_charge,
    COALESCE(labor.total_charge, 0) - COALESCE(labor.total_cost, 0) AS labor_profit,
    COALESCE(img.total_cost, 0)      AS imagery_cost,
    COALESCE(img.total_charge, 0)    AS imagery_charge,
    COALESCE(img.total_charge, 0) - COALESCE(img.total_cost, 0) AS imagery_profit,
    COALESCE(labor.total_charge, 0) + COALESCE(img.total_charge, 0) AS grand_total_charge,
    COALESCE(labor.total_cost, 0) + COALESCE(img.total_cost, 0) AS grand_total_cost,
    (COALESCE(labor.total_charge, 0) - COALESCE(labor.total_cost, 0))
    + (COALESCE(img.total_charge, 0) - COALESCE(img.total_cost, 0)) AS total_profit
FROM projects p
LEFT JOIN (
    SELECT project_id,
           SUM(employee_rate * hours) AS total_cost,
           SUM(bid_rate * hours)      AS total_charge
    FROM labor_entries GROUP BY project_id
) labor ON labor.project_id = p.id
LEFT JOIN (
    SELECT project_id,
           SUM(cost)   AS total_cost,
           SUM(charge) AS total_charge
    FROM imagery_orders GROUP BY project_id
) img ON img.project_id = p.id;

DROP VIEW IF EXISTS v_imagery_profit_by_provider;
CREATE VIEW v_imagery_profit_by_provider AS
SELECT
    provider,
    COUNT(*)      AS order_count,
    SUM(cost)     AS total_cost,
    SUM(charge)   AS total_charge,
    SUM(charge) - SUM(cost) AS profit
FROM imagery_orders
GROUP BY provider;

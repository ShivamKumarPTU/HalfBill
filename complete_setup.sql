-- ================================================================
-- OneBill Intern Program — Complete Database Setup Script
-- ================================================================
-- HOW TO RUN:
--
--   Step 1 (as postgres admin):
--     psql -U postgres -f complete_setup.sql
--
-- The script handles everything in order:
--   1. Creates role and user (as postgres admin)
--   2. Creates and configures the database (as postgres admin)
--   3. Switches to onebill_user
--   4. Creates all tables and indexes (as onebill_user)
--   5. Loads all seed data (as onebill_user)
--
-- Prerequisites:
--   - PostgreSQL 15+
--   - pgvector extension package installed on the OS
--     (e.g. sudo apt install postgresql-15-pgvector)
-- ================================================================


-- ================================================================
-- SECTION 1: ADMIN SETUP
-- Runs as postgres superuser
-- ================================================================

\echo '=========================================='
\echo 'SECTION 1: Admin Setup (postgres)'
\echo '=========================================='

-- Drop existing objects if re-running this script
DROP DATABASE IF EXISTS onebill;
DROP USER IF EXISTS onebill_user;
DROP ROLE IF EXISTS onebill_role;

-- ── Create role ───────────────────────────────────────────────
-- onebill_role has no login ability — it is a permission container
CREATE ROLE onebill_role
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT;

\echo 'Role onebill_role created.'

-- ── Create user ───────────────────────────────────────────────
-- onebill_user can log in and inherits onebill_role permissions
CREATE USER onebill_user
    WITH PASSWORD 'OneBill2025!'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    INHERIT
    LOGIN;

GRANT onebill_role TO onebill_user;

\echo 'User onebill_user created and assigned onebill_role.'

-- ── Create database ───────────────────────────────────────────
CREATE DATABASE onebill
    OWNER = onebill_user
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

\echo 'Database onebill created.'

-- ── Connect to the new database as admin ─────────────────────
\connect onebill postgres

-- ── Enable extensions (requires superuser) ───────────────────
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

\echo 'Extensions vector and uuid-ossp enabled.'

-- ── Grant schema privileges to the role ──────────────────────
-- onebill_user owns the database but we explicitly grant
-- schema-level privileges for clarity and good practice
GRANT ALL PRIVILEGES ON DATABASE onebill TO onebill_role;
GRANT ALL ON SCHEMA public TO onebill_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO onebill_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO onebill_role;

\echo 'Privileges granted to onebill_role.'
\echo ''
\echo 'Admin setup complete. Switching to onebill_user...'
\echo ''


-- ================================================================
-- SECTION 2: SCHEMA AND DATA
-- Switches to onebill_user — all tables owned by this user
-- ================================================================

\connect onebill onebill_user

\echo '=========================================='
\echo 'SECTION 2: Schema Creation (onebill_user)'
\echo '=========================================='


-- ================================================================
-- SHARED TABLES
-- ================================================================

CREATE TABLE customers (
    id              SERIAL PRIMARY KEY,
    customer_code   VARCHAR(20)   UNIQUE NOT NULL,
    name            VARCHAR(255)  NOT NULL,
    email           VARCHAR(255)  UNIQUE NOT NULL,
    phone           VARCHAR(20),
    account_type    VARCHAR(20)   NOT NULL
                        CHECK (account_type IN ('residential', 'business')),
    status          VARCHAR(20)   NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'suspended', 'churned')),
    address_line1   VARCHAR(255),
    city            VARCHAR(100),
    state           VARCHAR(50),
    zip             VARCHAR(10),
    lat             NUMERIC(9,6),
    lng             NUMERIC(9,6),
    monthly_spend   NUMERIC(10,2),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_customers_status       ON customers(status);
CREATE INDEX idx_customers_account_type ON customers(account_type);
CREATE INDEX idx_customers_city         ON customers(city);

\echo 'Table: customers'


CREATE TABLE products (
    id              SERIAL PRIMARY KEY,
    product_code    VARCHAR(50)   UNIQUE NOT NULL,
    name            VARCHAR(255)  NOT NULL,
    category        VARCHAR(30)   NOT NULL
                        CHECK (category IN ('internet','mobile','ott','equipment','installation','bundle')),
    billing_type    VARCHAR(20)   NOT NULL
                        CHECK (billing_type IN ('monthly','annual','one_time','prepaid')),
    contract_type   VARCHAR(20)   NOT NULL
                        CHECK (contract_type IN ('postpaid','prepaid','no_contract')),
    base_price      NUMERIC(10,2) NOT NULL,
    setup_fee       NUMERIC(10,2) DEFAULT 0,
    description     TEXT,
    specs           JSONB,
    is_active       BOOLEAN DEFAULT TRUE,
    embedding       vector(1024),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_products_category     ON products(category);
CREATE INDEX idx_products_billing_type ON products(billing_type);
CREATE INDEX idx_products_embedding
    ON products USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

\echo 'Table: products'


-- ================================================================
-- CPQ TABLES
-- ================================================================

CREATE TABLE cpq_quotes (
    id                  SERIAL PRIMARY KEY,
    quote_number        VARCHAR(20)   UNIQUE NOT NULL,
    customer_id         INTEGER       NOT NULL REFERENCES customers(id),
    status              VARCHAR(20)   NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft','presented','accepted','rejected','expired')),
    total_mrr           NUMERIC(10,2) DEFAULT 0,
    total_otc           NUMERIC(10,2) DEFAULT 0,
    total_value         NUMERIC(10,2) DEFAULT 0,
    discount_percent    NUMERIC(5,2)  DEFAULT 0,
    discount_reason     VARCHAR(255),
    valid_until         DATE,
    notes               TEXT,
    created_by          VARCHAR(100),
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cpq_quotes_customer ON cpq_quotes(customer_id);
CREATE INDEX idx_cpq_quotes_status   ON cpq_quotes(status);
CREATE INDEX idx_cpq_quotes_created  ON cpq_quotes(created_at);

\echo 'Table: cpq_quotes'


CREATE TABLE cpq_quote_line_items (
    id                  SERIAL PRIMARY KEY,
    quote_id            INTEGER       NOT NULL REFERENCES cpq_quotes(id) ON DELETE CASCADE,
    product_id          INTEGER       NOT NULL REFERENCES products(id),
    quantity            INTEGER       NOT NULL DEFAULT 1,
    list_price          NUMERIC(10,2) NOT NULL,
    discount_percent    NUMERIC(5,2)  DEFAULT 0,
    unit_price          NUMERIC(10,2) NOT NULL,
    subtotal            NUMERIC(10,2) NOT NULL,
    is_recurring        BOOLEAN       NOT NULL,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cpq_line_items_quote   ON cpq_quote_line_items(quote_id);
CREATE INDEX idx_cpq_line_items_product ON cpq_quote_line_items(product_id);

\echo 'Table: cpq_quote_line_items'


CREATE TABLE cpq_quote_status_history (
    id          SERIAL PRIMARY KEY,
    quote_id    INTEGER      NOT NULL REFERENCES cpq_quotes(id),
    old_status  VARCHAR(20),
    new_status  VARCHAR(20)  NOT NULL,
    changed_by  VARCHAR(100),
    notes       TEXT,
    changed_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cpq_status_history_quote ON cpq_quote_status_history(quote_id);

\echo 'Table: cpq_quote_status_history'


-- ================================================================
-- BILLING TABLES
-- ================================================================

CREATE TABLE billing_invoices (
    id                      SERIAL PRIMARY KEY,
    invoice_number          VARCHAR(20)   UNIQUE NOT NULL,
    customer_id             INTEGER       NOT NULL REFERENCES customers(id),
    quote_id                INTEGER       REFERENCES cpq_quotes(id),
    status                  VARCHAR(20)   NOT NULL DEFAULT 'draft'
                                CHECK (status IN ('draft','issued','paid','overdue','disputed','written_off')),
    billing_period_start    DATE,
    billing_period_end      DATE,
    due_date                DATE,
    subtotal                NUMERIC(10,2) NOT NULL,
    tax_rate                NUMERIC(5,2)  DEFAULT 8.5,
    tax_amount              NUMERIC(10,2) DEFAULT 0,
    total_amount            NUMERIC(10,2) NOT NULL,
    paid_amount             NUMERIC(10,2) DEFAULT 0,
    balance_due             NUMERIC(10,2) GENERATED ALWAYS AS (total_amount - paid_amount) STORED,
    currency                VARCHAR(3)    DEFAULT 'USD',
    notes                   TEXT,
    issued_at               TIMESTAMP,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_billing_invoices_customer ON billing_invoices(customer_id);
CREATE INDEX idx_billing_invoices_status   ON billing_invoices(status);
CREATE INDEX idx_billing_invoices_due      ON billing_invoices(due_date);
CREATE INDEX idx_billing_invoices_quote    ON billing_invoices(quote_id);

\echo 'Table: billing_invoices'


CREATE TABLE billing_invoice_line_items (
    id          SERIAL PRIMARY KEY,
    invoice_id  INTEGER       NOT NULL REFERENCES billing_invoices(id) ON DELETE CASCADE,
    product_id  INTEGER       REFERENCES products(id),
    description VARCHAR(255)  NOT NULL,
    quantity    INTEGER       DEFAULT 1,
    unit_price  NUMERIC(10,2) NOT NULL,
    subtotal    NUMERIC(10,2) NOT NULL,
    line_type   VARCHAR(20)
                    CHECK (line_type IN ('recurring','one_time','credit','adjustment','tax')),
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_billing_line_items_invoice ON billing_invoice_line_items(invoice_id);

\echo 'Table: billing_invoice_line_items'


CREATE TABLE billing_payments (
    id              SERIAL PRIMARY KEY,
    invoice_id      INTEGER       NOT NULL REFERENCES billing_invoices(id),
    customer_id     INTEGER       NOT NULL REFERENCES customers(id),
    amount          NUMERIC(10,2) NOT NULL,
    payment_method  VARCHAR(30)
                        CHECK (payment_method IN ('credit_card','bank_transfer','check','cash','auto_pay')),
    status          VARCHAR(20)
                        CHECK (status IN ('pending','completed','failed','refunded')),
    transaction_ref VARCHAR(100),
    paid_at         TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_billing_payments_invoice  ON billing_payments(invoice_id);
CREATE INDEX idx_billing_payments_customer ON billing_payments(customer_id);

\echo 'Table: billing_payments'


CREATE TABLE billing_anomalies (
    id              SERIAL PRIMARY KEY,
    invoice_id      INTEGER       NOT NULL REFERENCES billing_invoices(id),
    customer_id     INTEGER       NOT NULL REFERENCES customers(id),
    anomaly_type    VARCHAR(50)   NOT NULL
                        CHECK (anomaly_type IN (
                            'duplicate_charge','rate_mismatch','missing_credit',
                            'usage_spike','unauthorized_charge','billing_gap','overdue_balance'
                        )),
    severity        VARCHAR(20)   CHECK (severity IN ('low','medium','high','critical')),
    amount_affected NUMERIC(10,2),
    description     TEXT,
    status          VARCHAR(20)   DEFAULT 'open'
                        CHECK (status IN ('open','investigating','resolved','dismissed')),
    detected_at     TIMESTAMP DEFAULT NOW(),
    resolved_at     TIMESTAMP
);

CREATE INDEX idx_billing_anomalies_customer ON billing_anomalies(customer_id);
CREATE INDEX idx_billing_anomalies_status   ON billing_anomalies(status);
CREATE INDEX idx_billing_anomalies_severity ON billing_anomalies(severity);

\echo 'Table: billing_anomalies'


-- ================================================================
-- SERVICEDESK TABLES
-- ================================================================

CREATE TABLE servicedesk_categories (
    id                   SERIAL PRIMARY KEY,
    name                 VARCHAR(100) NOT NULL,
    product_area         VARCHAR(30)
                             CHECK (product_area IN ('internet','mobile','ott','billing','equipment','general')),
    default_priority     VARCHAR(20)  DEFAULT 'medium',
    requires_field_visit BOOLEAN      DEFAULT FALSE
);

\echo 'Table: servicedesk_categories'


CREATE TABLE servicedesk_tickets (
    id              SERIAL PRIMARY KEY,
    ticket_number   VARCHAR(20)   UNIQUE NOT NULL,
    customer_id     INTEGER       NOT NULL REFERENCES customers(id),
    invoice_id      INTEGER       REFERENCES billing_invoices(id),
    anomaly_id      INTEGER       REFERENCES billing_anomalies(id),
    category_id     INTEGER       REFERENCES servicedesk_categories(id),
    subject         VARCHAR(255)  NOT NULL,
    description     TEXT,
    status          VARCHAR(30)   NOT NULL DEFAULT 'open'
                        CHECK (status IN (
                            'open','in_progress','pending_customer',
                            'pending_field_visit','resolved','closed'
                        )),
    priority        VARCHAR(20)   NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('low','medium','high','critical')),
    channel         VARCHAR(20)   CHECK (channel IN ('phone','email','chat','portal','auto')),
    assigned_to     VARCHAR(100),
    resolution      TEXT,
    embedding       vector(1024),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    resolved_at     TIMESTAMP
);

CREATE INDEX idx_sd_tickets_customer ON servicedesk_tickets(customer_id);
CREATE INDEX idx_sd_tickets_status   ON servicedesk_tickets(status);
CREATE INDEX idx_sd_tickets_priority ON servicedesk_tickets(priority);
CREATE INDEX idx_sd_tickets_invoice  ON servicedesk_tickets(invoice_id);
CREATE INDEX idx_sd_tickets_anomaly  ON servicedesk_tickets(anomaly_id);
CREATE INDEX idx_sd_tickets_embedding
    ON servicedesk_tickets USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

\echo 'Table: servicedesk_tickets'


CREATE TABLE servicedesk_ticket_comments (
    id          SERIAL PRIMARY KEY,
    ticket_id   INTEGER      NOT NULL REFERENCES servicedesk_tickets(id) ON DELETE CASCADE,
    author      VARCHAR(100) NOT NULL,
    comment     TEXT         NOT NULL,
    is_internal BOOLEAN      DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sd_comments_ticket ON servicedesk_ticket_comments(ticket_id);

\echo 'Table: servicedesk_ticket_comments'


CREATE TABLE servicedesk_ticket_status_history (
    id          SERIAL PRIMARY KEY,
    ticket_id   INTEGER      NOT NULL REFERENCES servicedesk_tickets(id),
    old_status  VARCHAR(30),
    new_status  VARCHAR(30)  NOT NULL,
    changed_by  VARCHAR(100),
    notes       TEXT,
    changed_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sd_status_history_ticket ON servicedesk_ticket_status_history(ticket_id);

\echo 'Table: servicedesk_ticket_status_history'


-- ================================================================
-- FSM TABLES
-- ================================================================

CREATE TABLE fsm_technicians (
    id                SERIAL PRIMARY KEY,
    technician_code   VARCHAR(20)   UNIQUE NOT NULL,
    name              VARCHAR(255)  NOT NULL,
    email             VARCHAR(255),
    phone             VARCHAR(20),
    specializations   TEXT[]        NOT NULL,
    status            VARCHAR(20)   DEFAULT 'available'
                          CHECK (status IN ('available','on_job','off_duty','on_leave')),
    zone              VARCHAR(100),
    current_lat       NUMERIC(9,6),
    current_lng       NUMERIC(9,6),
    jobs_completed    INTEGER       DEFAULT 0,
    rating            NUMERIC(3,2)  DEFAULT 5.0,
    created_at        TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fsm_technicians_status ON fsm_technicians(status);
CREATE INDEX idx_fsm_technicians_zone   ON fsm_technicians(zone);

\echo 'Table: fsm_technicians'


CREATE TABLE fsm_jobs (
    id                    SERIAL PRIMARY KEY,
    job_number            VARCHAR(20)   UNIQUE NOT NULL,
    customer_id           INTEGER       NOT NULL REFERENCES customers(id),
    ticket_id             INTEGER       REFERENCES servicedesk_tickets(id),
    invoice_id            INTEGER       REFERENCES billing_invoices(id),
    job_type              VARCHAR(30)   NOT NULL
                              CHECK (job_type IN (
                                  'installation','repair','maintenance',
                                  'equipment_swap','inspection','disconnection'
                              )),
    status                VARCHAR(20)   NOT NULL DEFAULT 'pending'
                              CHECK (status IN (
                                  'pending','assigned','en_route',
                                  'in_progress','completed','cancelled','no_show'
                              )),
    priority              VARCHAR(20)   DEFAULT 'medium'
                              CHECK (priority IN ('low','medium','high','emergency')),
    description           TEXT,
    address_line1         VARCHAR(255),
    city                  VARCHAR(100),
    state                 VARCHAR(50),
    zip                   VARCHAR(10),
    job_lat               NUMERIC(9,6),
    job_lng               NUMERIC(9,6),
    scheduled_date        DATE,
    scheduled_start_time  TIME,
    scheduled_end_time    TIME,
    actual_start          TIMESTAMP,
    actual_end            TIMESTAMP,
    completion_notes      TEXT,
    parts_used            JSONB,
    created_at            TIMESTAMP DEFAULT NOW(),
    updated_at            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fsm_jobs_customer  ON fsm_jobs(customer_id);
CREATE INDEX idx_fsm_jobs_ticket    ON fsm_jobs(ticket_id);
CREATE INDEX idx_fsm_jobs_status    ON fsm_jobs(status);
CREATE INDEX idx_fsm_jobs_scheduled ON fsm_jobs(scheduled_date);

\echo 'Table: fsm_jobs'


CREATE TABLE fsm_job_assignments (
    id            SERIAL PRIMARY KEY,
    job_id        INTEGER   NOT NULL REFERENCES fsm_jobs(id),
    technician_id INTEGER   NOT NULL REFERENCES fsm_technicians(id),
    assigned_at   TIMESTAMP DEFAULT NOW(),
    is_primary    BOOLEAN   DEFAULT TRUE,
    UNIQUE(job_id, technician_id)
);

CREATE INDEX idx_fsm_assignments_job  ON fsm_job_assignments(job_id);
CREATE INDEX idx_fsm_assignments_tech ON fsm_job_assignments(technician_id);

\echo 'Table: fsm_job_assignments'


CREATE TABLE fsm_technician_schedules (
    id            SERIAL PRIMARY KEY,
    technician_id INTEGER      NOT NULL REFERENCES fsm_technicians(id),
    schedule_date DATE         NOT NULL,
    start_time    TIME         NOT NULL,
    end_time      TIME         NOT NULL,
    is_available  BOOLEAN      DEFAULT TRUE,
    notes         VARCHAR(255),
    UNIQUE(technician_id, schedule_date, start_time)
);

CREATE INDEX idx_fsm_schedules_tech ON fsm_technician_schedules(technician_id, schedule_date);

\echo 'Table: fsm_technician_schedules'
\echo ''
\echo 'All tables created. Loading seed data...'
\echo ''


-- ================================================================
-- SECTION 3: SEED DATA
-- ================================================================

\echo '=========================================='
\echo 'SECTION 3: Seed Data (onebill_user)'
\echo '=========================================='


-- ── Products (15 rows) ────────────────────────────────────────

\echo 'Loading products...'

INSERT INTO products
    (product_code, name, category, billing_type, contract_type, base_price, setup_fee, description, specs)
VALUES
('PRD-INT-100','Starter Broadband 100Mbps','internet','monthly','postpaid',
 39.99,0,'Entry-level cable broadband. Best for light browsing and single-device streaming.',
 '{"speed_down_mbps":100,"speed_up_mbps":20,"data_cap_gb":500,"technology":"cable"}'),

('PRD-INT-500','Standard Fiber 500Mbps','internet','monthly','postpaid',
 59.99,0,'Mid-tier fiber. Ideal for households with 3-5 users streaming simultaneously.',
 '{"speed_down_mbps":500,"speed_up_mbps":100,"data_cap_gb":null,"technology":"fiber"}'),

('PRD-INT-1G','Premium Fiber 1Gbps','internet','monthly','postpaid',
 89.99,0,'High-speed symmetric fiber for power users, remote workers, and large households.',
 '{"speed_down_mbps":1000,"speed_up_mbps":500,"data_cap_gb":null,"technology":"fiber"}'),

('PRD-INT-2G','Business Fiber 2Gbps','internet','monthly','postpaid',
 149.99,99.00,'Enterprise-grade symmetric fiber with 99.9% SLA. For small-medium businesses.',
 '{"speed_down_mbps":2000,"speed_up_mbps":2000,"data_cap_gb":null,"technology":"fiber","sla_uptime_pct":99.9}'),

('PRD-INT-ANN','Annual Fiber 500Mbps','internet','annual','postpaid',
 599.99,0,'Standard Fiber 500Mbps on annual commitment. Save 17% versus monthly.',
 '{"speed_down_mbps":500,"speed_up_mbps":100,"data_cap_gb":null,"technology":"fiber","equivalent_monthly":50.00}'),

('PRD-MOB-PP5','Mobile Prepaid 5GB','mobile','prepaid','prepaid',
 25.00,0,'Prepaid mobile. 5GB data, unlimited calls and texts. No contract.',
 '{"data_gb":5,"calls":"unlimited","sms":"unlimited","roaming":false,"lines":1}'),

('PRD-MOB-PP15','Mobile Prepaid 15GB','mobile','prepaid','prepaid',
 35.00,0,'Prepaid mobile with more data. 15GB, unlimited calls and texts.',
 '{"data_gb":15,"calls":"unlimited","sms":"unlimited","roaming":false,"lines":1}'),

('PRD-MOB-STD','Mobile Postpaid 20GB','mobile','monthly','postpaid',
 45.00,25.00,'Postpaid mobile. 20GB with rollover, unlimited calls and texts, international roaming.',
 '{"data_gb":20,"rollover":true,"calls":"unlimited","sms":"unlimited","roaming":true,"lines":1}'),

('PRD-MOB-UNL','Mobile Unlimited Postpaid','mobile','monthly','postpaid',
 65.00,25.00,'Unlimited everything. 10GB hotspot, roaming in 30 countries.',
 '{"data_gb":"unlimited","hotspot_gb":10,"calls":"unlimited","sms":"unlimited","roaming":true,"roaming_countries":30,"lines":1}'),

('PRD-MOB-FAM','Mobile Family Pack 4 Lines','mobile','monthly','postpaid',
 120.00,25.00,'Unlimited plan for four lines. Each line gets unlimited data and 10GB hotspot.',
 '{"data_gb":"unlimited","hotspot_gb":10,"calls":"unlimited","sms":"unlimited","lines":4,"roaming":true}'),

('PRD-OTT-BSC','StreamTV Basic','ott','monthly','no_contract',
 15.00,0,'50+ live channels. News, entertainment, kids. No sports or premium networks.',
 '{"channels":50,"streams_simultaneous":2,"sports":false,"premium_channels":false,"dvr_hours":20}'),

('PRD-OTT-PRM','StreamTV Premium','ott','monthly','no_contract',
 35.00,0,'150+ channels including live sports, HBO, and Showtime. Up to 5 simultaneous streams.',
 '{"channels":150,"streams_simultaneous":5,"sports":true,"premium_channels":true,"dvr_hours":200,"includes":["HBO","Showtime","ESPN+"]}'),

('PRD-EQP-RTR','Home WiFi 6 Router','equipment','one_time','no_contract',
 150.00,0,'Dual-band WiFi 6 router. Required for Fiber plans without compatible device.',
 '{"wifi_standard":"WiFi 6","bands":2,"warranty_years":2}'),

('PRD-EQP-SIM','SIM Card Activation','equipment','one_time','no_contract',
 25.00,0,'Physical or eSIM activation fee for new mobile lines.',
 '{"sim_type":["physical","esim"]}'),

('PRD-SVC-INST','Professional Installation','installation','one_time','no_contract',
 99.00,0,'On-site technician installation for Fiber or Business plans. Includes cable run and router setup.',
 '{"duration_hours":2,"includes_cable_run":true,"includes_router_setup":true}');

\echo 'Products loaded: 15 rows'


-- ── ServiceDesk Categories (12 rows) ─────────────────────────

\echo 'Loading servicedesk categories...'

INSERT INTO servicedesk_categories (name, product_area, default_priority, requires_field_visit) VALUES
('Internet Outage',       'internet',  'high',   true),
('Slow Internet Speed',   'internet',  'medium', false),
('WiFi Setup Issue',      'internet',  'medium', true),
('Mobile No Signal',      'mobile',    'high',   false),
('Mobile Data Issue',     'mobile',    'medium', false),
('SIM Replacement',       'mobile',    'low',    false),
('Streaming Not Working', 'ott',       'medium', false),
('Billing Dispute',       'billing',   'high',   false),
('Payment Not Credited',  'billing',   'medium', false),
('Equipment Fault',       'equipment', 'high',   true),
('Installation Request',  'general',   'medium', true),
('Account Management',    'general',   'low',    false);

\echo 'ServiceDesk categories loaded: 12 rows'


-- ── Customers (1,000 rows) ────────────────────────────────────

\echo 'Loading customers (1000 rows)...'

DO $$
DECLARE
    first_names  TEXT[] := ARRAY[
        'James','Mary','John','Patricia','Robert','Jennifer','Michael','Linda',
        'William','Barbara','David','Susan','Richard','Jessica','Joseph','Sarah',
        'Thomas','Karen','Charles','Lisa','Christopher','Nancy','Daniel','Betty',
        'Matthew','Margaret','Anthony','Sandra','Mark','Ashley','Donald','Dorothy',
        'Steven','Kimberly','Paul','Emily','Andrew','Donna','Joshua','Michelle'
    ];
    last_names   TEXT[] := ARRAY[
        'Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis',
        'Rodriguez','Martinez','Hernandez','Lopez','Gonzalez','Wilson','Anderson',
        'Thomas','Taylor','Moore','Jackson','Martin','Lee','Perez','Thompson',
        'White','Harris','Sanchez','Clark','Ramirez','Lewis','Robinson','Walker',
        'Young','Allen','King','Wright','Scott','Torres','Nguyen','Hill','Flores'
    ];
    cities       TEXT[] := ARRAY[
        'Austin','Dallas','Houston','San Antonio','Phoenix','Denver','Atlanta',
        'Charlotte','Nashville','Portland','Seattle','Minneapolis','Tampa','Orlando',
        'Las Vegas','Salt Lake City','Kansas City','Indianapolis','Columbus','Memphis'
    ];
    states       TEXT[] := ARRAY[
        'TX','TX','TX','TX','AZ','CO','GA',
        'NC','TN','OR','WA','MN','FL','FL',
        'NV','UT','MO','IN','OH','TN'
    ];
    zips         TEXT[] := ARRAY[
        '78701','75201','77001','78201','85001','80201','30301',
        '28201','37201','97201','98101','55401','33601','32801',
        '89101','84101','64101','46201','43201','38101'
    ];
    lats         NUMERIC[] := ARRAY[
        30.2672,32.7767,29.7604,29.4241,33.4484,39.7392,33.7490,
        35.2271,36.1627,45.5231,47.6062,44.9778,27.9506,28.5383,
        36.1699,40.7608,39.0997,39.7684,39.9612,35.1495
    ];
    lngs         NUMERIC[] := ARRAY[
        -97.7431,-96.7970,-95.3698,-98.4936,-112.0740,-104.9903,-84.3880,
        -80.8431,-86.7816,-122.6765,-122.3321,-93.2650,-82.4572,-81.3792,
        -115.1398,-111.8910,-94.5786,-86.1581,-82.9988,-90.0490
    ];
    account_types TEXT[] := ARRAY['residential','residential','residential','residential','business'];
    statuses      TEXT[] := ARRAY['active','active','active','active','active','active','active','suspended','suspended','churned'];
    fname        TEXT;
    lname        TEXT;
    city_idx     INTEGER;
    acct_type    TEXT;
    cust_status  TEXT;
    spend        NUMERIC;
    i            INTEGER;
BEGIN
    FOR i IN 1..1000 LOOP
        fname     := first_names[1 + floor(random() * array_length(first_names,1))::int];
        lname     := last_names[1 + floor(random() * array_length(last_names,1))::int];
        city_idx  := 1 + floor(random() * array_length(cities,1))::int;
        acct_type := account_types[1 + floor(random() * array_length(account_types,1))::int];
        cust_status := statuses[1 + floor(random() * array_length(statuses,1))::int];
        spend     := ROUND((30 + random() * 270)::numeric, 2);

        INSERT INTO customers (
            customer_code, name, email, phone,
            account_type, status,
            address_line1, city, state, zip,
            lat, lng, monthly_spend
        ) VALUES (
            'CUST-' || LPAD(i::text, 5, '0'),
            fname || ' ' || lname,
            LOWER(fname) || '.' || LOWER(lname) || i || '@email.com',
            '(' || (200 + floor(random()*800)::int)::text || ') ' ||
                LPAD(floor(random()*1000)::int::text,3,'0') || '-' ||
                LPAD(floor(random()*10000)::int::text,4,'0'),
            acct_type,
            cust_status,
            floor(100 + random()*9900)::int::text || ' ' ||
                last_names[1 + floor(random() * array_length(last_names,1))::int] || ' St',
            cities[city_idx],
            states[city_idx],
            zips[city_idx],
            lats[city_idx]  + (random()-0.5) * 0.2,
            lngs[city_idx]  + (random()-0.5) * 0.2,
            spend
        );
    END LOOP;
END $$;

\echo 'Customers loaded: 1000 rows'


-- ── FSM Technicians (25 rows) ─────────────────────────────────

\echo 'Loading FSM technicians...'

DO $$
DECLARE
    tech_names TEXT[] := ARRAY[
        'Carlos Mendez','Brian Walsh','Priya Patel','Marcus Thompson','Jenny Liu',
        'Derek Foster','Aisha Johnson','Tyler Brooks','Sofia Reyes','Nathan Kim',
        'Rachel Torres','James Okafor','Megan Larson','Diego Vargas','Amy Chen',
        'Kevin Murphy','Fatima Hassan','Luke Patterson','Diana Cruz','Sam Nguyen',
        'Chris Adams','Leila Ahmadi','Tony Russo','Hannah Scott','Omar Abdullah'
    ];
    zones TEXT[] := ARRAY[
        'North','North','North','North','North',
        'South','South','South','South','South',
        'East','East','East','East','East',
        'West','West','West','West','West',
        'Central','Central','Central','Central','Central'
    ];
    all_specs TEXT[][] := ARRAY[
        ARRAY['fiber','equipment'],
        ARRAY['fiber','installation'],
        ARRAY['mobile','equipment'],
        ARRAY['fiber','mobile','installation'],
        ARRAY['equipment','installation'],
        ARRAY['fiber'],
        ARRAY['mobile'],
        ARRAY['fiber','equipment','installation'],
        ARRAY['mobile','installation'],
        ARRAY['fiber','mobile']
    ];
    statuses TEXT[] := ARRAY[
        'available','available','available','available','available',
        'available','available','available','on_job','off_duty'
    ];
    base_lats NUMERIC[] := ARRAY[
        30.35,30.25,30.28,30.31,30.29,
        30.18,30.15,30.20,30.16,30.22,
        30.27,30.30,30.32,30.26,30.24,
        30.19,30.21,30.23,30.17,30.33,
        30.26,30.27,30.25,30.28,30.26
    ];
    base_lngs NUMERIC[] := ARRAY[
        -97.68,-97.72,-97.70,-97.69,-97.71,
        -97.75,-97.78,-97.74,-97.76,-97.73,
        -97.65,-97.67,-97.64,-97.66,-97.68,
        -97.80,-97.79,-97.81,-97.82,-97.63,
        -97.72,-97.71,-97.73,-97.70,-97.74
    ];
    spec_idx INTEGER;
    i INTEGER;
BEGIN
    FOR i IN 1..25 LOOP
        spec_idx := 1 + floor(random() * array_length(all_specs,1))::int;
        INSERT INTO fsm_technicians (
            technician_code, name, email, phone,
            specializations, status, zone,
            current_lat, current_lng,
            jobs_completed, rating
        ) VALUES (
            'TECH-' || LPAD(i::text, 3, '0'),
            tech_names[i],
            LOWER(REPLACE(tech_names[i],' ','.')) || '@onebill-field.com',
            '(512) ' || LPAD(floor(random()*1000)::int::text,3,'0') || '-' ||
                LPAD(floor(random()*10000)::int::text,4,'0'),
            all_specs[spec_idx],
            statuses[1 + floor(random() * array_length(statuses,1))::int],
            zones[i],
            base_lats[i] + (random()-0.5) * 0.05,
            base_lngs[i] + (random()-0.5) * 0.05,
            floor(random() * 200)::int,
            ROUND((3.5 + random() * 1.5)::numeric, 1)
        );
    END LOOP;
END $$;

\echo 'FSM technicians loaded: 25 rows'


-- ── FSM Technician Schedules (next 14 days) ───────────────────

\echo 'Loading FSM technician schedules...'

INSERT INTO fsm_technician_schedules (technician_id, schedule_date, start_time, end_time, is_available)
SELECT
    t.id,
    d.schedule_date,
    '08:00'::TIME,
    '17:00'::TIME,
    CASE WHEN random() < 0.85 THEN TRUE ELSE FALSE END
FROM fsm_technicians t
CROSS JOIN (
    SELECT generate_series(
        CURRENT_DATE,
        CURRENT_DATE + INTERVAL '14 days',
        INTERVAL '1 day'
    )::DATE AS schedule_date
) d
WHERE EXTRACT(DOW FROM d.schedule_date) NOT IN (0, 6);  -- weekdays only

\echo 'FSM schedules loaded.'


-- ── CPQ Quotes (~350 quotes with line items) ──────────────────

\echo 'Loading CPQ quotes and line items...'

DO $$
DECLARE
    quote_statuses TEXT[] := ARRAY[
        'accepted','accepted','accepted','accepted',
        'presented','presented',
        'draft','draft',
        'rejected',
        'expired'
    ];
    recurring_products INTEGER[];
    onetime_products   INTEGER[];
    sales_reps TEXT[] := ARRAY[
        'Alice Morgan','Ben Carter','Carmen Silva',
        'David Park','Elena Russo','Frank Osei'
    ];
    q_id         INTEGER;
    c_id         INTEGER;
    q_status     TEXT;
    q_number     TEXT;
    disc_pct     NUMERIC;
    disc_reason  TEXT;
    mrr          NUMERIC;
    otc          NUMERIC;
    prod_id      INTEGER;
    prod_price   NUMERIC;
    prod_recurring BOOLEAN;
    prod_unit_price NUMERIC;
    prod_subtotal   NUMERIC;
    valid_d      DATE;
    q_counter    INTEGER := 0;
BEGIN
    -- Get recurring and one-time product IDs
    SELECT ARRAY_AGG(id) INTO recurring_products
    FROM products WHERE billing_type IN ('monthly','annual');

    SELECT ARRAY_AGG(id) INTO onetime_products
    FROM products WHERE billing_type = 'one_time';

    FOR c_id IN
        SELECT id FROM customers
        WHERE status = 'active'
        ORDER BY random()
        LIMIT 350
    LOOP
        q_counter := q_counter + 1;
        q_status  := quote_statuses[1 + floor(random() * array_length(quote_statuses,1))::int];
        q_number  := 'QT-2024-' || LPAD(q_counter::text, 5, '0');
        disc_pct  := CASE WHEN random() < 0.3 THEN ROUND((random() * 20)::numeric, 1) ELSE 0 END;
        disc_reason := CASE WHEN disc_pct > 0 THEN
            (ARRAY['Competitive pricing','Loyalty discount','Bundle promotion','Annual commitment'])[floor(random()*4+1)::int]
            ELSE NULL END;
        valid_d   := CURRENT_DATE + (floor(random() * 30 + 15))::int;

        INSERT INTO cpq_quotes (
            quote_number, customer_id, status,
            discount_percent, discount_reason, valid_until,
            created_by,
            created_at, updated_at,
            total_mrr, total_otc, total_value
        ) VALUES (
            q_number, c_id, q_status,
            disc_pct, disc_reason, valid_d,
            sales_reps[1 + floor(random() * array_length(sales_reps,1))::int],
            NOW() - (floor(random() * 180))::int * INTERVAL '1 day',
            NOW() - (floor(random() * 30))::int * INTERVAL '1 day',
            0, 0, 0
        ) RETURNING id INTO q_id;

        mrr := 0;
        otc := 0;

        -- Add 1-2 recurring products
        FOR i IN 1..(1 + floor(random()*2)::int) LOOP
            prod_id := recurring_products[1 + floor(random() * array_length(recurring_products,1))::int];

            SELECT base_price,
                   billing_type NOT IN ('one_time')
            INTO prod_price, prod_recurring
            FROM products WHERE id = prod_id;

            prod_unit_price := ROUND(prod_price * (1 - disc_pct/100), 2);
            prod_subtotal   := prod_unit_price;

            INSERT INTO cpq_quote_line_items (
                quote_id, product_id, quantity,
                list_price, discount_percent, unit_price, subtotal, is_recurring
            ) VALUES (
                q_id, prod_id, 1,
                prod_price, disc_pct, prod_unit_price, prod_subtotal, TRUE
            );

            mrr := mrr + prod_subtotal;
        END LOOP;

        -- ~60% of quotes include a one-time product
        IF random() < 0.6 THEN
            prod_id := onetime_products[1 + floor(random() * array_length(onetime_products,1))::int];
            SELECT base_price INTO prod_price FROM products WHERE id = prod_id;
            prod_unit_price := prod_price;
            prod_subtotal   := prod_price;

            INSERT INTO cpq_quote_line_items (
                quote_id, product_id, quantity,
                list_price, discount_percent, unit_price, subtotal, is_recurring
            ) VALUES (
                q_id, prod_id, 1,
                prod_price, 0, prod_unit_price, prod_subtotal, FALSE
            );
            otc := otc + prod_subtotal;
        END IF;

        -- Update quote totals
        UPDATE cpq_quotes SET
            total_mrr   = mrr,
            total_otc   = otc,
            total_value = mrr + otc
        WHERE id = q_id;

        -- Status history
        INSERT INTO cpq_quote_status_history (quote_id, old_status, new_status, changed_by, changed_at)
        VALUES (q_id, NULL, 'draft',
            sales_reps[1 + floor(random() * array_length(sales_reps,1))::int],
            NOW() - (floor(random() * 180))::int * INTERVAL '1 day');

        IF q_status != 'draft' THEN
            INSERT INTO cpq_quote_status_history (quote_id, old_status, new_status, changed_by, changed_at)
            VALUES (q_id, 'draft', q_status,
                sales_reps[1 + floor(random() * array_length(sales_reps,1))::int],
                NOW() - (floor(random() * 60))::int * INTERVAL '1 day');
        END IF;

    END LOOP;
END $$;

\echo 'CPQ quotes and line items loaded.'


-- ── Billing Invoices (~600 rows) ──────────────────────────────

\echo 'Loading billing invoices, line items and payments...'

DO $$
DECLARE
    inv_statuses TEXT[] := ARRAY[
        'paid','paid','paid','paid','paid',
        'issued','issued',
        'overdue','overdue',
        'disputed',
        'written_off'
    ];
    inv_id      INTEGER;
    c_id        INTEGER;
    q_id        INTEGER;
    q_mrr       NUMERIC;
    q_otc       NUMERIC;
    inv_status  TEXT;
    inv_number  TEXT;
    subtotal    NUMERIC;
    tax_amt     NUMERIC;
    total_amt   NUMERIC;
    paid_amt    NUMERIC;
    period_start DATE;
    period_end   DATE;
    due_d        DATE;
    issued_d     TIMESTAMP;
    inv_counter  INTEGER := 0;
    pay_method   TEXT;
BEGIN
    -- Create invoices from accepted quotes
    FOR q_id, c_id, q_mrr, q_otc IN
        SELECT id, customer_id, total_mrr, total_otc
        FROM cpq_quotes
        WHERE status = 'accepted'
    LOOP
        inv_counter  := inv_counter + 1;
        inv_status   := inv_statuses[1 + floor(random() * array_length(inv_statuses,1))::int];
        inv_number   := 'INV-2024-' || LPAD(inv_counter::text, 5, '0');
        period_start := DATE_TRUNC('month', NOW() - (floor(random()*6))::int * INTERVAL '1 month')::DATE;
        period_end   := (period_start + INTERVAL '1 month - 1 day')::DATE;
        due_d        := period_end + 14;
        issued_d     := period_start + INTERVAL '1 day';
        subtotal     := ROUND((q_mrr + q_otc)::numeric, 2);
        tax_amt      := ROUND((subtotal * 0.085)::numeric, 2);
        total_amt    := subtotal + tax_amt;
        paid_amt     := CASE
                            WHEN inv_status = 'paid'     THEN total_amt
                            WHEN inv_status = 'issued'   THEN 0
                            WHEN inv_status = 'overdue'  THEN 0
                            WHEN inv_status = 'disputed' THEN ROUND((total_amt * random() * 0.5)::numeric, 2)
                            ELSE 0
                        END;

        INSERT INTO billing_invoices (
            invoice_number, customer_id, quote_id, status,
            billing_period_start, billing_period_end, due_date,
            subtotal, tax_rate, tax_amount, total_amount, paid_amount,
            issued_at, created_at, updated_at
        ) VALUES (
            inv_number, c_id, q_id, inv_status,
            period_start, period_end, due_d,
            subtotal, 8.5, tax_amt, total_amt, paid_amt,
            issued_d,
            issued_d,
            NOW()
        ) RETURNING id INTO inv_id;

        -- Line item: recurring charges
        IF q_mrr > 0 THEN
            INSERT INTO billing_invoice_line_items (invoice_id, description, unit_price, subtotal, line_type)
            VALUES (inv_id, 'Monthly recurring services', q_mrr, q_mrr, 'recurring');
        END IF;

        -- Line item: one-time charges
        IF q_otc > 0 THEN
            INSERT INTO billing_invoice_line_items (invoice_id, description, unit_price, subtotal, line_type)
            VALUES (inv_id, 'One-time charges', q_otc, q_otc, 'one_time');
        END IF;

        -- Tax line
        INSERT INTO billing_invoice_line_items (invoice_id, description, unit_price, subtotal, line_type)
        VALUES (inv_id, 'Tax (8.5%)', tax_amt, tax_amt, 'tax');

        -- Payment record for paid invoices
        IF inv_status = 'paid' THEN
            pay_method := (ARRAY['credit_card','bank_transfer','auto_pay','check'])[floor(random()*4+1)::int];
            INSERT INTO billing_payments (
                invoice_id, customer_id, amount, payment_method,
                status, transaction_ref, paid_at
            ) VALUES (
                inv_id, c_id, total_amt, pay_method,
                'completed',
                'TXN-' || UPPER(SUBSTRING(MD5(random()::text), 1, 10)),
                due_d - (floor(random()*5))::int * INTERVAL '1 day'
            );
        END IF;

    END LOOP;

    -- Add ~200 standalone invoices (no quote) for existing customers
    FOR c_id IN
        SELECT id FROM customers WHERE status IN ('active','suspended')
        ORDER BY random() LIMIT 200
    LOOP
        inv_counter  := inv_counter + 1;
        inv_status   := inv_statuses[1 + floor(random() * array_length(inv_statuses,1))::int];
        inv_number   := 'INV-2024-' || LPAD(inv_counter::text, 5, '0');
        period_start := DATE_TRUNC('month', NOW() - (floor(random()*6))::int * INTERVAL '1 month')::DATE;
        period_end   := (period_start + INTERVAL '1 month - 1 day')::DATE;
        due_d        := period_end + 14;
        issued_d     := period_start + INTERVAL '1 day';
        subtotal     := ROUND((40 + random() * 200)::numeric, 2);
        tax_amt      := ROUND((subtotal * 0.085)::numeric, 2);
        total_amt    := subtotal + tax_amt;
        paid_amt     := CASE
                            WHEN inv_status = 'paid' THEN total_amt
                            ELSE 0
                        END;

        INSERT INTO billing_invoices (
            invoice_number, customer_id, status,
            billing_period_start, billing_period_end, due_date,
            subtotal, tax_rate, tax_amount, total_amount, paid_amount,
            issued_at, created_at
        ) VALUES (
            inv_number, c_id, inv_status,
            period_start, period_end, due_d,
            subtotal, 8.5, tax_amt, total_amt, paid_amt,
            issued_d, issued_d
        ) RETURNING id INTO inv_id;

        INSERT INTO billing_invoice_line_items (invoice_id, description, unit_price, subtotal, line_type)
        VALUES (inv_id, 'Monthly services', subtotal, subtotal, 'recurring');

        IF inv_status = 'paid' THEN
            INSERT INTO billing_payments (
                invoice_id, customer_id, amount, payment_method, status,
                transaction_ref, paid_at
            ) VALUES (
                inv_id, c_id, total_amt,
                (ARRAY['credit_card','auto_pay','bank_transfer'])[floor(random()*3+1)::int],
                'completed',
                'TXN-' || UPPER(SUBSTRING(MD5(random()::text), 1, 10)),
                due_d - (floor(random()*3))::int * INTERVAL '1 day'
            );
        END IF;
    END LOOP;

END $$;

\echo 'Billing invoices, line items and payments loaded.'


-- ── Billing Anomalies (~80 rows) ──────────────────────────────

\echo 'Loading billing anomalies...'

INSERT INTO billing_anomalies (
    invoice_id, customer_id, anomaly_type, severity,
    amount_affected, description, status, detected_at
)
SELECT
    i.id,
    i.customer_id,
    (ARRAY['duplicate_charge','rate_mismatch','missing_credit',
            'usage_spike','unauthorized_charge','billing_gap','overdue_balance'])
        [floor(random()*7+1)::int],
    (ARRAY['low','medium','high','critical'])[floor(random()*4+1)::int],
    ROUND((10 + random() * 200)::numeric, 2),
    (ARRAY[
        'Charge appears twice in the same billing period.',
        'Billed rate does not match the contracted plan rate.',
        'Promotional credit was not applied to this invoice.',
        'Data usage 300% above customer historical average.',
        'Charge for a service not in the customer contract.',
        'No invoice generated for the previous billing period.',
        'Invoice overdue by more than 30 days with no payment.'
    ])[floor(random()*7+1)::int],
    (ARRAY['open','open','open','investigating','resolved','dismissed'])[floor(random()*6+1)::int],
    NOW() - (floor(random()*90))::int * INTERVAL '1 day'
FROM billing_invoices i
WHERE i.status IN ('overdue','disputed','written_off')
ORDER BY random()
LIMIT 80;

\echo 'Billing anomalies loaded: 80 rows'


-- ── ServiceDesk Tickets (~400 rows) ──────────────────────────

\echo 'Loading ServiceDesk tickets...'

DO $$
DECLARE
    tk_statuses  TEXT[] := ARRAY[
        'open','open','open',
        'in_progress','in_progress',
        'pending_customer',
        'pending_field_visit',
        'resolved','resolved',
        'closed'
    ];
    priorities   TEXT[] := ARRAY['low','medium','medium','medium','high','high','critical'];
    channels     TEXT[] := ARRAY['phone','phone','email','chat','portal'];
    agents       TEXT[] := ARRAY[
        'Support Team A','Support Team B','Support Team C',
        'Tier 2 - Network','Tier 2 - Billing','Auto-Triage'
    ];
    subjects     TEXT[] := ARRAY[
        'Internet is down completely',
        'My internet speed is very slow',
        'Cannot connect to WiFi',
        'No mobile signal at home',
        'Mobile data not working',
        'Streaming keeps buffering',
        'Charge on my bill I don''t recognize',
        'Payment was made but not showing',
        'My router keeps restarting',
        'Need fiber installation at new address',
        'Cancel my streaming add-on',
        'Update my billing address'
    ];
    tk_id        INTEGER;
    c_id         INTEGER;
    inv_id       INTEGER;
    anom_id      INTEGER;
    cat_id       INTEGER;
    tk_counter   INTEGER := 0;
    tk_status    TEXT;
    use_invoice  BOOLEAN;
    use_anomaly  BOOLEAN;
BEGIN
    FOR c_id IN
        SELECT id FROM customers
        ORDER BY random()
        LIMIT 400
    LOOP
        tk_counter := tk_counter + 1;
        tk_status  := tk_statuses[1 + floor(random() * array_length(tk_statuses,1))::int];
        cat_id     := 1 + floor(random() * 12)::int;
        use_invoice := random() < 0.25;
        use_anomaly := random() < 0.15;

        -- Optionally link to an invoice
        inv_id := NULL;
        IF use_invoice THEN
            SELECT id INTO inv_id FROM billing_invoices
            WHERE customer_id = c_id ORDER BY random() LIMIT 1;
        END IF;

        -- Optionally link to an anomaly
        anom_id := NULL;
        IF use_anomaly THEN
            SELECT id INTO anom_id FROM billing_anomalies
            WHERE customer_id = c_id ORDER BY random() LIMIT 1;
        END IF;

        INSERT INTO servicedesk_tickets (
            ticket_number, customer_id, invoice_id, anomaly_id,
            category_id, subject, description,
            status, priority, channel, assigned_to,
            created_at, updated_at,
            resolved_at
        ) VALUES (
            'TKT-2024-' || LPAD(tk_counter::text, 5, '0'),
            c_id, inv_id, anom_id,
            cat_id,
            subjects[1 + floor(random() * array_length(subjects,1))::int],
            'Customer reported this issue via ' ||
                channels[1 + floor(random() * array_length(channels,1))::int] || '. Awaiting investigation.',
            tk_status,
            priorities[1 + floor(random() * array_length(priorities,1))::int],
            channels[1 + floor(random() * array_length(channels,1))::int],
            agents[1 + floor(random() * array_length(agents,1))::int],
            NOW() - (floor(random() * 90))::int * INTERVAL '1 day',
            NOW() - (floor(random() * 10))::int * INTERVAL '1 day',
            CASE WHEN tk_status IN ('resolved','closed')
                 THEN NOW() - (floor(random() * 5))::int * INTERVAL '1 day'
                 ELSE NULL END
        ) RETURNING id INTO tk_id;

        -- Add 1-2 comments
        INSERT INTO servicedesk_ticket_comments (ticket_id, author, comment, is_internal, created_at)
        VALUES (
            tk_id,
            agents[1 + floor(random() * array_length(agents,1))::int],
            (ARRAY[
                'Ticket received and assigned. Initial diagnostics started.',
                'Contacted customer — confirmed the issue. Escalating to Tier 2.',
                'Network team investigating. No ETA yet.',
                'Issue linked to regional outage. Monitoring.',
                'Customer confirmed issue is resolved. Closing ticket.'
            ])[floor(random()*5+1)::int],
            random() < 0.3,
            NOW() - (floor(random() * 5))::int * INTERVAL '1 day'
        );

    END LOOP;
END $$;

\echo 'ServiceDesk tickets loaded: ~400 rows'


-- ── FSM Jobs (~250 rows) ──────────────────────────────────────

\echo 'Loading FSM jobs...'

DO $$
DECLARE
    job_types   TEXT[] := ARRAY[
        'installation','installation',
        'repair','repair','repair',
        'maintenance',
        'equipment_swap',
        'inspection',
        'disconnection'
    ];
    job_statuses TEXT[] := ARRAY[
        'completed','completed','completed',
        'assigned','assigned',
        'in_progress',
        'pending',
        'cancelled',
        'no_show'
    ];
    priorities  TEXT[] := ARRAY['low','medium','medium','high','emergency'];
    j_id        INTEGER;
    c_id        INTEGER;
    tk_id       INTEGER;
    tech_id     INTEGER;
    j_type      TEXT;
    j_status    TEXT;
    sched_date  DATE;
    j_counter   INTEGER := 0;
BEGIN
    FOR c_id IN
        SELECT id FROM customers
        ORDER BY random()
        LIMIT 250
    LOOP
        j_counter := j_counter + 1;
        j_type    := job_types[1 + floor(random() * array_length(job_types,1))::int];
        j_status  := job_statuses[1 + floor(random() * array_length(job_statuses,1))::int];
        sched_date := CURRENT_DATE + (floor(random()*30 - 10))::int;

        -- Optionally link to a ticket
        tk_id := NULL;
        IF random() < 0.5 THEN
            SELECT id INTO tk_id
            FROM servicedesk_tickets
            WHERE customer_id = c_id
            AND status IN ('pending_field_visit','in_progress','open')
            ORDER BY random() LIMIT 1;
        END IF;

        -- Pick a random technician
        SELECT id INTO tech_id FROM fsm_technicians ORDER BY random() LIMIT 1;

        INSERT INTO fsm_jobs (
            job_number, customer_id, ticket_id,
            job_type, status,
            priority, description,
            address_line1, city, state, zip,
            scheduled_date, scheduled_start_time, scheduled_end_time,
            actual_start, actual_end, completion_notes,
            created_at, updated_at
        )
        SELECT
            'JOB-2024-' || LPAD(j_counter::text, 5, '0'),
            c_id, tk_id,
            j_type, j_status,
            priorities[1 + floor(random() * array_length(priorities,1))::int],
            INITCAP(j_type) || ' job for customer ' || customer_code,
            address_line1, city, state, zip,
            sched_date, '09:00'::TIME, '11:00'::TIME,
            CASE WHEN j_status IN ('in_progress','completed')
                 THEN sched_date::TIMESTAMP + INTERVAL '9 hours' ELSE NULL END,
            CASE WHEN j_status = 'completed'
                 THEN sched_date::TIMESTAMP + INTERVAL '10 hours 30 minutes' ELSE NULL END,
            CASE WHEN j_status = 'completed'
                 THEN 'Job completed successfully. Customer confirmed service is working.'
                 ELSE NULL END,
            NOW() - (floor(random()*60))::int * INTERVAL '1 day',
            NOW()
        FROM customers WHERE id = c_id
        RETURNING id INTO j_id;

        -- Assign technician
        IF j_status NOT IN ('pending','cancelled') THEN
            INSERT INTO fsm_job_assignments (job_id, technician_id, is_primary)
            VALUES (j_id, tech_id, TRUE)
            ON CONFLICT (job_id, technician_id) DO NOTHING;
        END IF;

    END LOOP;
END $$;

\echo 'FSM jobs loaded: ~250 rows'


-- ================================================================
-- VERIFICATION
-- ================================================================

\echo ''
\echo '=========================================='
\echo 'VERIFICATION — Row Counts'
\echo '=========================================='

SELECT
    'customers'               AS table_name, COUNT(*) AS rows FROM customers
UNION ALL SELECT 'products',                 COUNT(*) FROM products
UNION ALL SELECT 'cpq_quotes',               COUNT(*) FROM cpq_quotes
UNION ALL SELECT 'cpq_quote_line_items',     COUNT(*) FROM cpq_quote_line_items
UNION ALL SELECT 'cpq_quote_status_history', COUNT(*) FROM cpq_quote_status_history
UNION ALL SELECT 'billing_invoices',         COUNT(*) FROM billing_invoices
UNION ALL SELECT 'billing_invoice_line_items', COUNT(*) FROM billing_invoice_line_items
UNION ALL SELECT 'billing_payments',         COUNT(*) FROM billing_payments
UNION ALL SELECT 'billing_anomalies',        COUNT(*) FROM billing_anomalies
UNION ALL SELECT 'servicedesk_categories',   COUNT(*) FROM servicedesk_categories
UNION ALL SELECT 'servicedesk_tickets',      COUNT(*) FROM servicedesk_tickets
UNION ALL SELECT 'servicedesk_ticket_comments', COUNT(*) FROM servicedesk_ticket_comments
UNION ALL SELECT 'servicedesk_ticket_status_history', COUNT(*) FROM servicedesk_ticket_status_history
UNION ALL SELECT 'fsm_technicians',          COUNT(*) FROM fsm_technicians
UNION ALL SELECT 'fsm_jobs',                 COUNT(*) FROM fsm_jobs
UNION ALL SELECT 'fsm_job_assignments',      COUNT(*) FROM fsm_job_assignments
UNION ALL SELECT 'fsm_technician_schedules', COUNT(*) FROM fsm_technician_schedules
ORDER BY table_name;

\echo ''
\echo '=========================================='
\echo 'Setup complete. Database is ready.'
\echo 'Connect string: psql -U onebill_user -d onebill -h localhost'
\echo '=========================================='

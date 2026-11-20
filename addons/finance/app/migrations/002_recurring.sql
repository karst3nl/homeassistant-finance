-- Wiederkehrende Buchungen (Fixkosten) und Herkunft automatischer Buchungen.

CREATE TABLE recurring_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    direction TEXT NOT NULL CHECK (direction IN ('expense', 'income')),
    interval TEXT NOT NULL CHECK (interval IN ('monthly', 'yearly')),
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    start_date TEXT NOT NULL,
    next_due TEXT NOT NULL,
    counterparty TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Bestehende Datenbanken bekommen die neuen Spalten; NULL = manuelle Buchung.
ALTER TABLE transactions ADD COLUMN recurring_rule_id INTEGER
    REFERENCES recurring_rules(id) ON DELETE SET NULL;
ALTER TABLE transactions ADD COLUMN recurring_period TEXT;

-- Verhindert doppelte Buchungen, auch wenn die Erzeugung mehrfach läuft.
CREATE UNIQUE INDEX idx_transactions_recurring
    ON transactions (recurring_rule_id, recurring_period)
    WHERE recurring_rule_id IS NOT NULL;

CREATE INDEX idx_recurring_next_due ON recurring_rules (next_due);

PRAGMA user_version = 2;

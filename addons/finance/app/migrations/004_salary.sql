-- Monatsgehalt als eigener Bereich, bewusst getrennt von den Fixkosten.
--
-- Eine Regel beschreibt eine monatliche Einnahme. Die erzeugten Buchungen
-- liegen ganz normal in `transactions`, tragen source = 'salary' und zählen
-- daher zu den Einnahmen. salary_rule_id + salary_period verhindern Duplikate.

CREATE TABLE salary_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
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

ALTER TABLE transactions ADD COLUMN salary_rule_id INTEGER
    REFERENCES salary_rules(id) ON DELETE SET NULL;
ALTER TABLE transactions ADD COLUMN salary_period TEXT;

-- Pro Gehaltsregel und Monat höchstens eine Buchung.
CREATE UNIQUE INDEX idx_transactions_salary
    ON transactions (salary_rule_id, salary_period)
    WHERE salary_rule_id IS NOT NULL;

CREATE INDEX idx_salary_next_due ON salary_rules (next_due);

PRAGMA user_version = 4;

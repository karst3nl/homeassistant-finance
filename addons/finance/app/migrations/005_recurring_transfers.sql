-- Wiederkehrende Umbuchungen als Option einer Fixkostenregel.
--
-- `account_id` ist bei einer Umbuchung das Quellkonto, `to_account_id` das Zielkonto.
-- Erzeugt wird ein normaler Eintrag in `transfers` mit zwei Buchungen. Herkunft
-- und Zeitraum werden am Transfer gespeichert, damit ein Monat nicht doppelt
-- gebucht wird. Die CHECK-Regel von `recurring_rules` muss dafür erweitert
-- werden, daher wird die Tabelle unter Beibehaltung aller Zeilen neu angelegt.

-- Fremdschlüssel werden für den Tabellentausch kurz abgeschaltet; sonst
-- schreibt SQLite die Referenz in `transactions` beim Umbenennen um.
PRAGMA foreign_keys = OFF;
PRAGMA legacy_alter_table = ON;

ALTER TABLE recurring_rules RENAME TO recurring_rules_old;

CREATE TABLE recurring_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    direction TEXT NOT NULL CHECK (direction IN ('expense', 'income', 'transfer')),
    interval TEXT NOT NULL CHECK (interval IN ('monthly', 'yearly')),
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    to_account_id INTEGER REFERENCES accounts(id) ON DELETE RESTRICT,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    start_date TEXT NOT NULL,
    next_due TEXT NOT NULL,
    counterparty TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (to_account_id IS NULL OR to_account_id <> account_id),
    CHECK ((direction = 'transfer') = (to_account_id IS NOT NULL))
);

INSERT INTO recurring_rules (
    id, name, amount_cents, direction, interval, account_id, to_account_id,
    category_id, start_date, next_due, counterparty, description, active,
    created_at, updated_at
)
SELECT
    id, name, amount_cents, direction, interval, account_id, NULL,
    category_id, start_date, next_due, counterparty, description, active,
    created_at, updated_at
FROM recurring_rules_old;

DROP TABLE recurring_rules_old;

CREATE INDEX idx_recurring_next_due ON recurring_rules (next_due);

ALTER TABLE transfers ADD COLUMN recurring_rule_id INTEGER
    REFERENCES recurring_rules(id) ON DELETE SET NULL;
ALTER TABLE transfers ADD COLUMN recurring_period TEXT;

-- Pro Regel und Zeitraum höchstens eine automatische Umbuchung.
CREATE UNIQUE INDEX idx_transfers_recurring
    ON transfers (recurring_rule_id, recurring_period)
    WHERE recurring_rule_id IS NOT NULL;

PRAGMA legacy_alter_table = OFF;
PRAGMA foreign_keys = ON;

PRAGMA user_version = 5;

-- Umbuchungen zwischen zwei Konten.
--
-- Eine Umbuchung besteht aus einem Datensatz in `transfers` und genau zwei
-- Buchungen in `transactions`: eine negative auf dem Quellkonto und eine
-- positive auf dem Zielkonto. Beide tragen source = 'transfer' und werden
-- daher nicht als Einnahme/Ausgabe in Budgets und Auswertungen gezählt.

CREATE TABLE transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    from_account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    to_account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (from_account_id <> to_account_id)
);

ALTER TABLE transactions ADD COLUMN transfer_id INTEGER
    REFERENCES transfers(id) ON DELETE CASCADE;

-- Pro Umbuchung genau eine Buchung je Konto. Verhindert halbe oder doppelte Paare.
CREATE UNIQUE INDEX idx_transactions_transfer_account
    ON transactions (transfer_id, account_id)
    WHERE transfer_id IS NOT NULL;

CREATE INDEX idx_transfers_date ON transfers (booking_date DESC);

PRAGMA user_version = 3;

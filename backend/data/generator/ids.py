"""Deterministic synthetic identifier generator."""


class IdGenerator:
    """Generates sequential, realistic, clearly synthetic business identifiers."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        self._payment_counter = 0
        self._order_counter = 0
        self._settlement_counter = 0
        self._utr_counter = 0
        self._event_counter = 0
        self._ledger_counter = 0
        self._case_counter = 0

    def next_payment_id(self) -> str:
        self._payment_counter += 1
        return f"PAY-{self._payment_counter:06d}"

    def next_order_id(self) -> str:
        self._order_counter += 1
        return f"ORD-{self._order_counter:06d}"

    def next_settlement_id(self) -> str:
        self._settlement_counter += 1
        return f"SET-{self._settlement_counter:06d}"

    def next_utr_number(self, bank_code: str = "HDFC") -> str:
        self._utr_counter += 1
        return f"UTR-SYN-{bank_code}-{self._utr_counter:06d}"

    def next_dispute_event_id(self) -> str:
        self._event_counter += 1
        return f"EVT-{self._event_counter:06d}"

    def next_ledger_id(self) -> str:
        self._ledger_counter += 1
        return f"LED-{self._ledger_counter:06d}"

    def next_case_id(self, scenario_tag: str) -> str:
        self._case_counter += 1
        return f"CASE-{scenario_tag.upper()}-{self._case_counter:04d}"

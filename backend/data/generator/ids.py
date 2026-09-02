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

    def _p(self) -> str:
        if not self.prefix:
            return ""
        return f"{self.prefix.rstrip('-')}-"

    def next_payment_id(self) -> str:
        self._payment_counter += 1
        return f"PAY-{self._p()}{self._payment_counter:06d}"

    def next_order_id(self) -> str:
        self._order_counter += 1
        return f"ORD-{self._p()}{self._order_counter:06d}"

    def next_settlement_id(self) -> str:
        self._settlement_counter += 1
        return f"SET-{self._p()}{self._settlement_counter:06d}"

    def next_utr_number(self, bank_code: str = "HDFC") -> str:
        self._utr_counter += 1
        return f"UTR-SYN-{self._p()}{bank_code}-{self._utr_counter:06d}"

    def next_dispute_event_id(self) -> str:
        self._event_counter += 1
        return f"EVT-{self._p()}{self._event_counter:06d}"

    def next_ledger_id(self) -> str:
        self._ledger_counter += 1
        return f"LED-{self._p()}{self._ledger_counter:06d}"

    def next_case_id(self, scenario_tag: str) -> str:
        self._case_counter += 1
        return f"CASE-{self._p()}{scenario_tag.upper()}-{self._case_counter:04d}"

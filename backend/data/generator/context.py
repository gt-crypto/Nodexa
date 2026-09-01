"""Generation context tracking seeded PRNG, identifiers, and financial entity accumulators."""
import random
from typing import List
from datetime import datetime, timedelta

from backend.data.generator.config import GeneratorConfig
from backend.data.generator.ids import IdGenerator
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.enums import LedgerEntryType


# Standard synthetic merchant & acquirer pools
MERCHANT_POOL = [
    "mer_retail_kart",
    "mer_tech_gadgets",
    "mer_travel_hub",
    "mer_groceries_express",
    "mer_fashion_hub",
    "mer_health_plus",
]

ACQUIRER_POOL = [
    {"id": "acq_hdfc_bank", "code": "HDFC"},
    {"id": "acq_icici_bank", "code": "ICICI"},
    {"id": "acq_axis_bank", "code": "AXIS"},
    {"id": "acq_sbi_bank", "code": "SBI"},
]


class GenerationContext:
    """Encapsulates deterministic state and accumulators for dataset generation."""

    def __init__(self, seed: int, config: GeneratorConfig):
        self.seed = seed
        self.config = config
        self.rng = random.Random(seed)
        self.ids = IdGenerator()
        
        # Cumulative running ledger balance in integer minor units (starting with synthetic ₹10,000,000 baseline)
        self.current_ledger_balance = 1_000_000_000  # ₹10,000,000.00
        
        # Accumulators
        self.gateway_transactions: List[GatewayTransaction] = []
        self.settlement_batches: List[BankSettlementBatch] = []
        self.merchant_orders: List[MerchantOrder] = []
        self.dispute_events: List[DisputeRefundEvent] = []
        self.ledger_entries: List[NodalLedgerEntry] = []
        self.ground_truth_cases: List[EvaluationGroundTruth] = []

    def random_merchant(self) -> str:
        return self.rng.choice(MERCHANT_POOL)

    def random_acquirer(self) -> dict:
        return self.rng.choice(ACQUIRER_POOL)

    def random_amount(self, min_inr: int = 500, max_inr: int = 50000) -> int:
        """Generates random monetary amount in integer minor units (paisa)."""
        rupees = self.rng.randint(min_inr, max_inr)
        return rupees * 100

    def add_ledger_entry(
        self,
        transaction_id: str | None,
        debit: int,
        credit: int,
        timestamp: datetime,
        entry_type: str,
        reference: str,
        account_id: str = "nodal_escrow_main",
    ) -> NodalLedgerEntry:
        """Records double-entry ledger mutation and updates running balance deterministically."""
        self.current_ledger_balance = self.current_ledger_balance + credit - debit
        entry = NodalLedgerEntry(
            ledger_id=self.ids.next_ledger_id(),
            transaction_id=transaction_id,
            account_id=account_id,
            debit=debit,
            credit=credit,
            balance_after=self.current_ledger_balance,
            timestamp=timestamp,
            entry_type=entry_type,
            reference=reference,
        )
        self.ledger_entries.append(entry)
        return entry

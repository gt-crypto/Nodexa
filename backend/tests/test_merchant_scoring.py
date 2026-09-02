import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.merchants.scoring import MerchantScoringService
from backend.models.merchant_score import MerchantScore
from backend.models.financial_sources import GatewayTransaction
from backend.models.exceptions import ExceptionRecord
from backend.models.enums import ExceptionSeverity, ExceptionState

def test_merchant_scoring_deterministic_logic(db_session: Session):
    # Setup test data
    merchant_id = "TEST_MERCHANT_999"
    
    # 1. Add some transactions to establish base volume
    gtx1 = GatewayTransaction(
        payment_id="PAY_TEST_1",
        merchant_id=merchant_id,
        amount=100000, # 1000 INR
        currency="INR",
        status="CAPTURED",
        method="UPI"
    )
    gtx2 = GatewayTransaction(
        payment_id="PAY_TEST_2",
        merchant_id=merchant_id,
        amount=50000, # 500 INR
        currency="INR",
        status="CAPTURED",
        method="UPI"
    )
    db_session.add(gtx1)
    db_session.add(gtx2)
    
    # 2. Add an exception for PAY_TEST_1
    exc1 = ExceptionRecord(
        exception_id="EXC_TEST_1",
        exception_type="GHOST_SETTLEMENT",
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DETECTED.value,
        exposure=100000,
        primary_payment_id="PAY_TEST_1",
        source_flag="seeded"
    )
    db_session.add(exc1)
    db_session.commit()
    
    # 3. Calculate Score
    service = MerchantScoringService()
    scores = service.calculate_all_scores(db_session)
    
    # Check if our merchant got a score
    ms = next((s for s in scores if s.merchant_id == merchant_id), None)
    assert ms is not None
    
    # Assert deterministic outputs
    assert ms.total_transaction_count == 2
    assert ms.total_transaction_volume == 150000
    assert ms.exception_count == 1
    assert ms.high_risk_exception_count == 1
    assert ms.total_exposure == 100000
    assert ms.seeded_case_count == 1
    
    # Verify trust score penalties
    # exc_rate = 1/2 = 0.5 -> penalty 40
    # high risk = 1 -> penalty 10
    # base 100 - 40 - 10 = 50
    assert ms.trust_score == 50
    assert ms.score_band == "WATCH"
    
    # Verify impact score
    # exposure = 1000 INR = 0 impact points (requires 10k for 1 point)
    # high risk = 1 -> 10 impact points
    assert ms.impact_score == 10

"""Fictional customer and mock peer cohort for the Phase 1 demo."""

from datetime import date

from app.simulation.models import CustomerProfile, PeerCohort

# Fixed clock so goal dates do not drift between runs.
AS_OF = date(2026, 9, 30)

# Mock consumer-loan rate for the demo. Not a KBC quote.
MOCK_CAR_APR = 0.059

HORIZON_MONTHS = 36
GOAL_SEARCH_MONTHS = 360

ALEX = CustomerProfile(
    name="Alex",
    monthly_net_income=3200,
    savings=18500,
    monthly_housing=900,
    monthly_fixed_other=550,
    monthly_variable=850,
    emergency_months_goal=6,
    apartment_goal=40000,
)

# Aggregated stand-in for "financially similar" profiles. Invented for the demo.
SIMILAR_PROFILES = PeerCohort(
    label="Similar Financial Profiles",
    income_band="€3,000–€3,500 per month",
    fixed_cost_ratio=0.42,
    savings_rate=0.22,
    runway_after_similar_purchase_months=4.8,
    traits=(
        "Income €3,000–€3,500 net",
        "Fixed costs around 42% of income",
        "Typical savings rate around 22%",
        "Housing, fixed bills, and variable spending in a similar mix",
    ),
)

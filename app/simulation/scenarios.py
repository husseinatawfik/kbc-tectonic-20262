"""Turn a customer and a decision into two parallel futures."""

from app.simulation.engine import SimulationInputError, monthly_payment, project_path
from app.simulation.explain import euro, format_date, peer_statements, tradeoff_statements
from app.simulation.models import CustomerProfile, MonthlyAdjustment, PathProjection, PeerCohort


def car_adjustment(
    *,
    price: float,
    down_payment: float,
    annual_interest_rate: float,
    term_months: int,
) -> tuple[MonthlyAdjustment, float, float, float]:
    if price <= 0:
        raise SimulationInputError("Car price must be greater than zero.")
    if price > 250000:
        raise SimulationInputError("Car price is outside the demo range.")
    if down_payment < 0:
        raise SimulationInputError("Down payment cannot be negative.")
    if term_months < 1 or term_months > 120:
        raise SimulationInputError("Loan duration must be between 1 and 120 months.")
    if annual_interest_rate < 0 or annual_interest_rate > 0.25:
        raise SimulationInputError("Interest rate is outside the demo range.")

    down = money_min(down_payment, price)
    principal = round(price - down, 2)
    payment = monthly_payment(principal, annual_interest_rate, term_months)
    adjustment = MonthlyAdjustment(
        opening_savings_delta=-down,
        extra_monthly_expense=payment,
        start_month=1,
        end_month=term_months,
    )
    return adjustment, payment, principal, down


def money_min(left: float, right: float) -> float:
    return round(min(left, right), 2)


def simulate_parallel_car(
    profile: CustomerProfile,
    cohort: PeerCohort,
    *,
    as_of,
    price: float,
    down_payment: float,
    loan_years: int,
    annual_interest_rate: float,
    horizon_months: int,
    search_months: int,
) -> dict:
    if loan_years < 1 or loan_years > 10:
        raise SimulationInputError("Loan duration must be between 1 and 10 years.")

    term_months = loan_years * 12
    adjustment, payment, principal, down = car_adjustment(
        price=price,
        down_payment=down_payment,
        annual_interest_rate=annual_interest_rate,
        term_months=term_months,
    )
    current = project_path(
        profile,
        "current",
        "Current Path",
        None,
        as_of=as_of,
        horizon_months=horizon_months,
        search_months=search_months,
    )
    car = project_path(
        profile,
        "buy_car",
        "Buy the car",
        adjustment,
        as_of=as_of,
        horizon_months=horizon_months,
        search_months=search_months,
        monthly_loan_payment=payment,
        amount_financed=principal,
        down_payment_applied=down,
        recurring_months=term_months,
    )
    rate_label = f"{annual_interest_rate:.1%} APR"
    return {
        "as_of": as_of.isoformat(),
        "horizon_months": horizon_months,
        "customer": _customer_payload(profile),
        "assumptions": {
            "annual_interest_rate": annual_interest_rate,
            "annual_interest_rate_label": rate_label,
            "note": (
                "Both paths start from today's savings. On the car path, the down payment "
                "is withdrawn in month 1, and the loan payment reduces disposable income "
                "until the term ends. Fuel, insurance, and maintenance are not included. "
                f"The interest rate is a mock {rate_label}."
            ),
        },
        "scenarios": [_scenario_payload(current), _scenario_payload(car)],
        "comparison": {
            "statements": tradeoff_statements(current, car),
        },
        "peers": {
            "label": cohort.label,
            "disclaimer": "Synthetic demo data. These figures are not drawn from real KBC customers.",
            "traits": list(cohort.traits),
            "statements": peer_statements(profile, car, cohort),
        },
    }


def _customer_payload(profile: CustomerProfile) -> dict:
    expenses = round(profile.monthly_expenses, 2)
    return {
        "name": profile.name,
        "savings": round(profile.savings, 2),
        "monthly_net_income": round(profile.monthly_net_income, 2),
        "monthly_housing": round(profile.monthly_housing, 2),
        "monthly_fixed_other": round(profile.monthly_fixed_other, 2),
        "monthly_variable": round(profile.monthly_variable, 2),
        "monthly_expenses": expenses,
        "monthly_disposable_income": round(profile.monthly_disposable_income, 2),
        "emergency_runway_months": round(profile.savings / expenses, 2),
        "emergency_months_goal": profile.emergency_months_goal,
        "apartment_goal": round(profile.apartment_goal, 2),
        "apartment_progress": round(profile.savings / profile.apartment_goal, 4),
        "fixed_cost_ratio": round(profile.fixed_cost_ratio, 4),
        "savings_rate": round(profile.savings_rate, 4),
    }


def _scenario_payload(path: PathProjection) -> dict:
    year_one = path.point(min(12, len(path.points) - 1))
    year_three = path.point(len(path.points) - 1)
    after_decision = path.point(1)
    return {
        "id": path.scenario_id,
        "label": path.label,
        "monthly_loan_payment": path.monthly_loan_payment,
        "amount_financed": path.amount_financed,
        "down_payment_applied": path.down_payment_applied,
        "monthly_disposable_income": path.monthly_disposable_income,
        "recurring_months": path.recurring_months,
        "savings_after_down_payment": round(path.points[0].savings + (-path.down_payment_applied), 2),
        "savings_after_1_year": year_one.savings,
        "savings_after_3_years": year_three.savings,
        "emergency_runway_after_decision": after_decision.emergency_runway_months,
        "emergency_runway_after_3_years": year_three.emergency_runway_months,
        "months_to_apartment_goal": path.months_to_apartment_goal,
        "apartment_goal_date": None
        if path.apartment_goal_date is None
        else path.apartment_goal_date.isoformat(),
        "apartment_goal_label": format_date(path.apartment_goal_date)
        or "Not reached within 30 years",
        "series": [
            {
                "month": point.month,
                "savings": point.savings,
                "monthly_disposable_income": point.monthly_disposable_income,
                "monthly_expenses": point.monthly_expenses,
                "emergency_runway_months": point.emergency_runway_months,
                "loan_payment": point.loan_payment,
            }
            for point in path.points
        ],
    }


def euro_text(amount: float) -> str:
    return euro(amount)

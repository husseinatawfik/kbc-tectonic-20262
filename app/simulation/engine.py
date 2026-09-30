"""Month-by-month projection.

Savings next month equal savings today plus disposable income. Disposable
income is net income minus housing, other fixed costs, variable spending, and
any recurring cost from the decision. A one-time cash movement, such as a down
payment, is applied at the start of the decision month.
"""

import calendar
from datetime import date

from app.simulation.models import (
    CustomerProfile,
    MonthPoint,
    MonthlyAdjustment,
    PathProjection,
)


class SimulationInputError(ValueError):
    """The caller sent a decision the engine will not project."""


def money(amount: float) -> float:
    return round(amount, 2)


def monthly_payment(principal: float, annual_interest_rate: float, term_months: int) -> float:
    """Standard amortizing payment, rounded to cents."""

    if term_months <= 0:
        raise SimulationInputError("Loan duration must be at least one month.")
    if principal <= 0:
        return 0.0
    monthly_rate = annual_interest_rate / 12
    if monthly_rate == 0:
        return money(principal / term_months)
    growth = (1 + monthly_rate) ** term_months
    raw = principal * monthly_rate * growth / (growth - 1)
    return money(raw)


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def runway_months(savings: float, expenses: float) -> float:
    if expenses <= 0:
        return 0.0
    return round(savings / expenses, 2)


def project_path(
    profile: CustomerProfile,
    scenario_id: str,
    label: str,
    adjustment: MonthlyAdjustment | None,
    *,
    as_of: date,
    horizon_months: int,
    search_months: int,
    monthly_loan_payment: float = 0.0,
    amount_financed: float = 0.0,
    down_payment_applied: float = 0.0,
    recurring_months: int | None = None,
) -> PathProjection:
    if horizon_months < 1:
        raise SimulationInputError("Horizon must cover at least one month.")
    if search_months < horizon_months:
        raise SimulationInputError("Goal search must cover the horizon.")

    baseline_expenses = money(profile.monthly_expenses)
    points: list[MonthPoint] = [
        _point(
            month=0,
            savings=money(profile.savings),
            expenses=baseline_expenses,
            disposable=money(profile.monthly_disposable_income),
            loan_payment=0.0,
        )
    ]

    savings = money(profile.savings)
    goal_month = 0 if savings >= profile.apartment_goal else None
    active_disposable = money(profile.monthly_disposable_income)

    for month in range(1, search_months + 1):
        income = profile.monthly_net_income
        extra_expense = 0.0
        loan_payment = 0.0
        if adjustment is not None and month == adjustment.start_month:
            savings = money(savings + adjustment.opening_savings_delta)
        if adjustment is not None and adjustment.recurring_on(month):
            income += adjustment.income_delta
            extra_expense = adjustment.extra_monthly_expense
            loan_payment = monthly_loan_payment if monthly_loan_payment else extra_expense
        expenses = money(baseline_expenses + extra_expense)
        disposable = money(income - expenses)
        if adjustment is not None and adjustment.recurring_on(month):
            active_disposable = disposable
        savings = money(savings + disposable)
        if goal_month is None and savings >= profile.apartment_goal:
            goal_month = month
        if month <= horizon_months:
            points.append(
                _point(
                    month=month,
                    savings=savings,
                    expenses=expenses,
                    disposable=disposable,
                    loan_payment=money(loan_payment),
                )
            )
        if month >= horizon_months and goal_month is not None:
            break

    goal_date = None if goal_month is None else add_months(as_of, goal_month)
    return PathProjection(
        scenario_id=scenario_id,
        label=label,
        points=tuple(points),
        monthly_loan_payment=money(monthly_loan_payment),
        amount_financed=money(amount_financed),
        down_payment_applied=money(down_payment_applied),
        monthly_disposable_income=active_disposable,
        recurring_months=recurring_months,
        months_to_apartment_goal=goal_month,
        apartment_goal_date=goal_date,
    )


def _point(
    *,
    month: int,
    savings: float,
    expenses: float,
    disposable: float,
    loan_payment: float,
) -> MonthPoint:
    return MonthPoint(
        month=month,
        savings=savings,
        monthly_expenses=expenses,
        monthly_disposable_income=disposable,
        emergency_runway_months=runway_months(savings, expenses),
        loan_payment=loan_payment,
    )

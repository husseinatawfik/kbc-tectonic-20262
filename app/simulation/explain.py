"""Neutral descriptions of a projection.

These sentences report differences. They do not tell the customer what to do.
"""

from app.simulation.models import CustomerProfile, PathProjection, PeerCohort


def euro(amount: float) -> str:
    sign = "-" if amount < 0 else ""
    cents = int(round(abs(amount) * 100))
    whole, remainder = divmod(cents, 100)
    body = f"{whole:,}"
    if remainder:
        return f"{sign}€{body}.{remainder:02d}"
    return f"{sign}€{body}"


def format_date(value) -> str | None:
    if value is None:
        return None
    return f"{value.day} {value.strftime('%B %Y')}"


def tradeoff_statements(current: PathProjection, alternative: PathProjection) -> list[str]:
    statements: list[str] = []
    current_months = current.months_to_apartment_goal
    other_months = alternative.months_to_apartment_goal

    if current_months is not None and other_months is not None:
        delay = other_months - current_months
        if delay > 0:
            statements.append(
                f"This scenario delays your apartment goal by approximately {delay} months."
            )
        elif delay < 0:
            statements.append(
                f"This scenario brings your apartment goal forward by approximately {-delay} months."
            )
        else:
            statements.append(
                "This scenario reaches your apartment goal on the same schedule as the current path."
            )
    elif other_months is None and current_months is not None:
        statements.append(
            "Within 30 years, this scenario does not reach the €40,000 apartment deposit. "
            f"The current path reaches it in {current_months} months."
        )
    elif other_months is not None and current_months is None:
        statements.append(
            "This scenario reaches the apartment deposit within 30 years. The current path does not."
        )
    else:
        statements.append("Neither path reaches the apartment deposit within 30 years.")

    horizon = min(len(current.points), len(alternative.points)) - 1
    year_one = min(12, horizon)
    year_three = horizon
    statements.append(
        f"After 1 year, projected savings are {euro(alternative.point(year_one).savings)} "
        f"on this path and {euro(current.point(year_one).savings)} on the current path."
    )
    statements.append(
        f"After 3 years, projected savings are {euro(alternative.point(year_three).savings)} "
        f"on this path and {euro(current.point(year_three).savings)} on the current path."
    )
    statements.append(
        f"Monthly disposable income is {euro(alternative.monthly_disposable_income)} "
        "while this decision's recurring cost is active, compared with "
        f"{euro(current.monthly_disposable_income)} on the current path."
    )
    statements.append(
        "One month after the decision, emergency runway is "
        f"{alternative.point(1).emergency_runway_months:.1f} months, compared with "
        f"{current.point(1).emergency_runway_months:.1f} months on the current path."
    )
    if alternative.recurring_months and alternative.monthly_loan_payment > 0:
        statements.append(
            f"Loan payments of {euro(alternative.monthly_loan_payment)} continue for "
            f"{alternative.recurring_months} months. Disposable income then returns to "
            f"{euro(current.monthly_disposable_income)}."
        )
    return statements


def peer_statements(
    profile: CustomerProfile,
    alternative: PathProjection,
    cohort: PeerCohort,
) -> list[str]:
    runway = alternative.point(1).emergency_runway_months
    return [
        (
            "Comparable financial profiles typically maintain around "
            f"{cohort.runway_after_similar_purchase_months:.1f} months of emergency savings "
            "after a similar purchase. In this simulation Alex would retain approximately "
            f"{runway:.1f} months."
        ),
        (
            f"The synthetic cohort reflects net income of {cohort.income_band}, a fixed-cost "
            f"ratio around {cohort.fixed_cost_ratio:.0%}, and a savings rate around "
            f"{cohort.savings_rate:.0%}. Alex's fixed costs are {profile.fixed_cost_ratio:.0%} "
            f"of net income, and the current savings rate is {profile.savings_rate:.0%}."
        ),
    ]

"""Deterministic checks for the projection engine and the demo API."""

import json
import threading
import unittest
from urllib.request import Request, urlopen

from app.data.synthetic import ALEX, AS_OF, MOCK_CAR_APR
from app.server import make_server
from app.simulation.engine import SimulationInputError, monthly_payment, project_path
from app.simulation.models import MonthlyAdjustment
from app.simulation.scenarios import simulate_parallel_car
from app.data.synthetic import GOAL_SEARCH_MONTHS, HORIZON_MONTHS, SIMILAR_PROFILES

FORBIDDEN = (
    "bad decision",
    "you should",
    "you shouldn't",
    "don't buy",
    "do not buy",
    "poor choice",
    "mistake",
    "irresponsible",
    "unwise",
)


def simulate(**overrides):
    payload = dict(
        price=30000,
        down_payment=5000,
        loan_years=5,
    )
    payload.update(overrides)
    return simulate_parallel_car(
        ALEX,
        SIMILAR_PROFILES,
        as_of=AS_OF,
        annual_interest_rate=MOCK_CAR_APR,
        horizon_months=HORIZON_MONTHS,
        search_months=GOAL_SEARCH_MONTHS,
        **payload,
    )


class PaymentTests(unittest.TestCase):
    def test_known_amortization(self):
        principal = 10000
        annual = 0.06
        months = 36
        monthly_rate = annual / 12
        growth = (1 + monthly_rate) ** months
        expected = round(principal * monthly_rate * growth / (growth - 1), 2)
        self.assertEqual(monthly_payment(principal, annual, months), expected)
        self.assertEqual(expected, 304.22)

    def test_zero_interest_splits_evenly(self):
        self.assertEqual(monthly_payment(10000, 0, 2), 5000)


class ProjectionTests(unittest.TestCase):
    def test_current_path_saves_the_full_surplus(self):
        result = simulate()
        current = result["scenarios"][0]
        self.assertEqual(current["id"], "current")
        self.assertEqual(current["savings_after_1_year"], 18500 + 900 * 12)
        self.assertEqual(current["savings_after_3_years"], 18500 + 900 * 36)
        self.assertEqual(current["months_to_apartment_goal"], 24)
        self.assertEqual(current["apartment_goal_date"], "2028-09-30")
        self.assertEqual(current["monthly_disposable_income"], 900)

    def test_car_path_withdraws_the_down_payment_and_charges_the_loan(self):
        result = simulate()
        car = result["scenarios"][1]
        payment = monthly_payment(25000, MOCK_CAR_APR, 60)
        self.assertEqual(car["amount_financed"], 25000)
        self.assertEqual(car["down_payment_applied"], 5000)
        self.assertEqual(car["monthly_loan_payment"], payment)
        self.assertEqual(car["monthly_disposable_income"], round(900 - payment, 2))
        self.assertEqual(car["series"][0]["savings"], 18500)
        self.assertEqual(car["series"][1]["savings"], round(18500 - 5000 + (900 - payment), 2))
        self.assertLess(car["savings_after_3_years"], result["scenarios"][0]["savings_after_3_years"])
        self.assertGreater(car["months_to_apartment_goal"], 24)

    def test_loan_end_restores_disposable_income(self):
        adjustment = MonthlyAdjustment(
            opening_savings_delta=-2000,
            extra_monthly_expense=5000,
            start_month=1,
            end_month=2,
        )
        path = project_path(
            ALEX,
            "cash_flow",
            "Short loan",
            adjustment,
            as_of=AS_OF,
            horizon_months=4,
            search_months=12,
            monthly_loan_payment=5000,
            recurring_months=2,
        )
        self.assertEqual(path.point(1).savings, 18500 - 2000 + (900 - 5000))
        self.assertEqual(path.point(2).savings, path.point(1).savings + (900 - 5000))
        self.assertEqual(path.point(3).monthly_disposable_income, 900)
        self.assertEqual(path.point(3).savings, path.point(2).savings + 900)

    def test_income_gap_uses_the_same_adjustment_model(self):
        gap = MonthlyAdjustment(
            income_delta=-ALEX.monthly_net_income,
            start_month=1,
            end_month=6,
        )
        path = project_path(
            ALEX,
            "leave",
            "Six months away",
            gap,
            as_of=AS_OF,
            horizon_months=12,
            search_months=36,
        )
        self.assertEqual(path.point(6).monthly_disposable_income, -2300)
        self.assertLess(path.point(6).savings, path.point(0).savings)
        self.assertEqual(path.point(7).monthly_disposable_income, 900)

    def test_down_payment_cannot_exceed_the_price(self):
        result = simulate(price=20000, down_payment=50000, loan_years=4)
        car = result["scenarios"][1]
        self.assertEqual(car["down_payment_applied"], 20000)
        self.assertEqual(car["amount_financed"], 0)
        self.assertEqual(car["monthly_loan_payment"], 0)

    def test_same_inputs_always_match(self):
        self.assertEqual(simulate(), simulate())


class LanguageTests(unittest.TestCase):
    def test_copy_describes_tradeoffs_without_advice(self):
        result = simulate()
        text = json.dumps(result["comparison"]["statements"] + result["peers"]["statements"]).lower()
        self.assertIn("delays your apartment goal by approximately", text)
        self.assertIn("synthetic", result["peers"]["disclaimer"].lower())
        self.assertIn("4.8 months", result["peers"]["statements"][0])
        self.assertIn("alex would retain approximately", result["peers"]["statements"][0].lower())
        for phrase in FORBIDDEN:
            self.assertNotIn(phrase, text)

    def test_invalid_duration_is_rejected(self):
        with self.assertRaises(SimulationInputError):
            simulate(loan_years=0)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_page_and_simulation_endpoint(self):
        with urlopen(f"http://127.0.0.1:{self.port}/") as response:
            page = response.read().decode()
            self.assertEqual(response.status, 200)
            self.assertIn("KBC Parallel", page)
            self.assertIn("/static/app.js", page)

        body = json.dumps({"car_price": 30000, "down_payment": 5000, "loan_years": 5}).encode()
        request = Request(
            f"http://127.0.0.1:{self.port}/api/simulate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            payload = json.load(response)
        self.assertEqual(payload["customer"]["name"], "Alex")
        self.assertEqual(len(payload["scenarios"]), 2)
        self.assertEqual(payload["scenarios"][0]["series"][0]["savings"], 18500)
        self.assertNotEqual(
            payload["scenarios"][0]["savings_after_3_years"],
            payload["scenarios"][1]["savings_after_3_years"],
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import ConsumptionLog, Food, MealInterval, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 3, 26, 9, 0, 0)


class LastConsumptionApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = User()
            user.username = "ana"
            user.email = "ana@example.com"
            user.set_password("secret")
            db.session.add(user)
            db.session.flush()

            self.user_id = user.id

            # Active interval at fixed now: 09:00 falls in breakfast.
            breakfast = MealInterval(user_id=user.id, name="Desayuno", start_time=datetime.strptime("08:00", "%H:%M").time(), end_time=datetime.strptime("10:00", "%H:%M").time(), target_hc=30)
            lunch = MealInterval(user_id=user.id, name="Almuerzo", start_time=datetime.strptime("13:00", "%H:%M").time(), end_time=datetime.strptime("15:00", "%H:%M").time(), target_hc=40)
            db.session.add_all([breakfast, lunch])

            base_food = Food(nombre="Manzana", hidratos_por_100g=12.0, user_id=None)
            db.session.add(base_food)
            db.session.flush()

            override_food = Food(nombre="Manzana Roja", hidratos_por_100g=13.0, user_id=user.id, parent_id=base_food.id)
            db.session.add(override_food)
            db.session.flush()

            self.base_food_id = base_food.id
            self.override_food_id = override_food.id

            db.session.commit()

        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_uses_last_consumption_in_same_active_interval_within_60_days(self):
        with self.app.app_context():
            db.session.add_all(
                [
                    # Same interval (desayuno), should be selected.
                    ConsumptionLog(
                        user_id=self.user_id,
                        food_id=self.base_food_id,
                        cantidad_gramos=42.0,
                        carbohidratos_calculados=8.2,
                        fecha_hora=datetime(2026, 3, 21, 9, 10, 0),
                    ),
                    # Newer but different interval, should be ignored while matching active interval.
                    ConsumptionLog(
                        user_id=self.user_id,
                        food_id=self.override_food_id,
                        cantidad_gramos=80.0,
                        carbohidratos_calculados=20.0,
                        fecha_hora=datetime(2026, 3, 23, 14, 0, 0),
                    ),
                ]
            )
            db.session.commit()

        with patch("app.main.datetime", FixedDateTime):
            response = self.client.get(f"/api/last_consumption/{self.override_food_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["found"])
        self.assertEqual(payload["cantidad_gramos"], 42.0)
        self.assertEqual(payload["cantidad_rc"], 1.0)

    def test_fallbacks_to_latest_any_interval_when_no_same_interval_in_60_days(self):
        with self.app.app_context():
            db.session.add_all(
                [
                    # Same interval but older than 60 days, should not be used for primary search.
                    ConsumptionLog(
                        user_id=self.user_id,
                        food_id=self.base_food_id,
                        cantidad_gramos=33.0,
                        carbohidratos_calculados=9.8,
                        fecha_hora=datetime(2025, 12, 20, 9, 5, 0),
                    ),
                    # Latest overall consumption, should be used by fallback.
                    ConsumptionLog(
                        user_id=self.user_id,
                        food_id=self.base_food_id,
                        cantidad_gramos=55.0,
                        carbohidratos_calculados=12.6,
                        fecha_hora=datetime(2026, 3, 24, 14, 10, 0),
                    ),
                ]
            )
            db.session.commit()

        with patch("app.main.datetime", FixedDateTime):
            response = self.client.get(f"/api/last_consumption/{self.override_food_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["found"])
        self.assertEqual(payload["cantidad_gramos"], 55.0)
        self.assertEqual(payload["cantidad_rc"], 1.5)


if __name__ == "__main__":
    unittest.main()


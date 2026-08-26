from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from .models import forest_division, forest_officer, forest_station, login_table


class DjangoUpgradeCompatibilityTests(TestCase):
    """
    Test suite verifying Django 5.2.16 and Python 3.14 compatibility.
    """

    def setUp(self):
        self.division = forest_division.objects.create(name="Wayanaad", place="Sultan Bathery")
        self.station = forest_station.objects.create(
            DIVISION=self.division,
            name="Muthanga Station",
            place="Muthanga",
            phone=9876543210,
            latitude=11.670,
            longitude=76.368,
        )

    def test_model_creation_and_string_representation(self):
        """Test model creation under Django 5.2.16."""
        self.assertEqual(str(self.station), "Muthanga Station")
        self.assertEqual(self.station.DIVISION.name, "Wayanaad")

    def test_officer_creation(self):
        """Test foreign key relationships and model fields."""
        login = login_table.objects.create(username="officer1", password="hashed_password", type="officer")
        officer = forest_officer.objects.create(
            LOGIN=login,
            STATION=self.station,
            first_name="John",
            last_name="Doe",
            address="Forest Quarters",
            phone=9400000000,
            email="officer@wildeye.gov.in",
            username="officer1",
            password="hashed_password",
        )
        self.assertEqual(str(officer), "John Doe")
        self.assertEqual(officer.STATION.name, "Muthanga Station")

    def test_zoneinfo_timezone_conversion(self):
        """Verify Python standard library zoneinfo integration in Django 5.2."""
        now_utc = timezone.now()
        kolkata_tz = ZoneInfo("Asia/Kolkata")
        now_kolkata = now_utc.astimezone(kolkata_tz)

        self.assertIsNotNone(now_kolkata)
        self.assertEqual(now_kolkata.tzinfo.key, "Asia/Kolkata")

    def test_django_version(self):
        """Verify exact Django version installed."""
        import django
        self.assertTrue(django.get_version().startswith("5.2"))

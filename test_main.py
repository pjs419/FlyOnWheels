import subprocess
import sys
import sqlite3
import unittest
from pathlib import Path

from create_database import DB_PATH, create_database

# Test inputs for the complete scenario
GIVEN_TEST_INPUTS = [
    "1",                                    # Main menu: 1 = Log in
    "Bob",                                  # Username
    "pqr123#!",                             # Password
    
    "1",                                    # Admin menu: 1 = View existing services
    "2",                                    # Admin menu: 2 = Create a service
    "Dublin to Dundalk, 2pm",               # Service name
    "3",                                    # Admin menu: 3 = Log out
    
    "2",                                    # Main menu: 2 = Create an account
    "Betty",                                # Username
    "x1-y2-z3",                             # Password
    
    "1",                                    # Main menu: 1 = Log in
    "Betty",                                # Username
    "x1-y2-z3",                             # Password
    
    "1",                                    # Customer menu: 1 = View future bus runs
    "2",                                    # Customer menu: 2 = Buy tickets
    "1",                                    # Select run number 1
    "2",                                    # Number of tickets
    "",                                     # Confirm booking (Enter)
    
    "3",                                    # Customer menu: 3 = View my tickets
    
    "2",                                    # Customer menu: 2 = Buy tickets
    "2",                                    # Select run number 2
    "1",                                    # Number of tickets
    "esc",                                  # Cancel booking
    
    "3",                                    # Customer menu: 3 = View my tickets
    
    "2",                                    # Customer menu: 2 = Buy tickets
    "3",                                    # Select run number 3
    "100",                                  # Number of tickets (will fail - not enough available)
    
    "4",                                    # Customer menu: 4 = Log out
    "3",                                    # Main menu: 3 = Exit
]


class TestTransportBookingSystem(unittest.TestCase):
    """Test the transport booking system with the given scenario."""

    SCRIPT_PATH = Path(__file__).resolve().parent / "main.py"

    def _run_main_with_inputs(self) -> str:
        input_data = "\n".join(GIVEN_TEST_INPUTS) + "\n"
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT_PATH)],
            cwd=str(self.SCRIPT_PATH.parent),
            input=input_data,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"main.py exited with {result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            ),
        )
        return result.stdout

    def setUp(self):
        """Reset the database before each test."""
        create_database()

    def test_complete_scenario(self):
        """
        Test the complete scenario:
        - Bob (admin) logs in, views services, creates a new service, logs out
        - Betty (customer) creates account, logs in, views services
        - Betty buys 2 tickets for service 1
        - Betty views her tickets
        - Betty attempts to buy 1 ticket for service 2 then cancels
        - Betty views her tickets again
        - Betty attempts to buy 100 tickets for service 3 (fails - not enough available)
        - Betty logs out and exits
        """
        output = self._run_main_with_inputs()

        # Verify key parts of the scenario appeared in this exact order.
        self.assertRegex(
            output,
            (
                r"(?s)=== Transport Booking System ===.*?"
                r"Welcome back, Bob!.*?"
                r"Service 'Dublin to Dundalk, 2pm' created.*?"
                r"Account created for 'Betty'.*?"
                r"Welcome back, Betty!.*?"
                r"Booking confirmed!.*?"
                r"Booking cancelled\."
            ),
        )

    def test_database_state_after_scenario(self):
        """Verify the database state is correct after the scenario."""
        self._run_main_with_inputs()

        # Verify database state
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check that new service was created
            services = cursor.execute(
                "SELECT COUNT(*) as cnt FROM service WHERE name = 'Dublin to Dundalk, 2pm'"
            ).fetchone()
            self.assertEqual(services["cnt"], 1)

            service = cursor.execute(
                "SELECT id FROM service WHERE name = 'Dublin to Dundalk, 2pm'"
            ).fetchone()
            self.assertIsNotNone(service)

            buses = cursor.execute(
                "SELECT COUNT(*) as cnt FROM bus WHERE service_id = ?",
                (service["id"],),
            ).fetchone()
            self.assertEqual(buses["cnt"], 2)

            runs = cursor.execute(
                "SELECT COUNT(*) as cnt FROM run WHERE service_id = ?",
                (service["id"],),
            ).fetchone()
            self.assertEqual(runs["cnt"], 7)

            # Check that Betty account was created
            betty = cursor.execute(
                "SELECT * FROM user WHERE username = 'Betty'"
            ).fetchone()
            self.assertIsNotNone(betty)
            self.assertEqual(betty["admin"], 0)

            # Check that Betty has one ticket row with total quantity 2
            tickets = cursor.execute(
                "SELECT COUNT(*) as cnt, COALESCE(SUM(number), 0) as total "
                "FROM ticket WHERE user_id = ?",
                (betty["id"],),
            ).fetchone()
            self.assertEqual(tickets["cnt"], 1)
            self.assertEqual(tickets["total"], 2)

            # Verify the ticket is for the selected run's service.
            ticket_details = cursor.execute(
                """
                SELECT t.number, s.name
                FROM ticket t
                JOIN run r ON t.run_id = r.id
                JOIN service s ON r.service_id = s.id
                WHERE t.user_id = ?
                """,
                (betty["id"],),
            ).fetchone()
            self.assertEqual(ticket_details["number"], 2)
            self.assertIn("Dublin to Dundalk", ticket_details["name"])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()

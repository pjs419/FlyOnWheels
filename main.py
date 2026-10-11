"""Menu-driven transport booking system for FlyOnWheels."""

import hashlib
import sqlite3
from datetime import datetime, timedelta

from create_database import DB_PATH, create_database

MODEL_A_NAME = "A"
MODEL_B_NAME = "B"
RUNS_CREATED_PER_SERVICE = 7
RUNS_ON_WEEKEND = "weekend"
RUNS_ON_WORKDAY = "workday"

# === Helper functions for database connection and common tasks ===
def _connect():
	"""Create and return a SQLite connection configured for row access by key."""
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row
	return conn


def _hash_password(raw_password):
	"""Return a SHA-256 hash for the provided raw password string."""
	return hashlib.sha256(raw_password.encode()).hexdigest()


def _prompt_menu_choice(prompt, valid_choices):
	"""Read a menu choice and keep prompting until a valid value is entered."""
	while True:
		choice = input(prompt).strip()
		if choice in valid_choices:
			return choice
		print("Invalid choice. Please try again.")

# === Functions for user authentication and account management ===
def login(conn):
	"""Authenticate a user by username and password and return the user row."""
	username = input("Username: ").strip()
	password = input("Password: ").strip()
	password_hash = _hash_password(password)

	user = conn.execute(
		"SELECT id, admin, username FROM user WHERE username = ? AND password = ?",
		(username, password_hash),
	).fetchone()

	if not user:
		print("Login failed.")
		return None

	print(f"Welcome back, {user['username']}!")
	return user


def create_account(conn):
	"""Create a new non-admin user account if the username is not already taken."""
	username = input("Choose a username: ").strip()
	password = input("Choose a password: ").strip()

	if not username or not password:
		print("Username and password are required.")
		return

	existing = conn.execute(
		"SELECT id FROM user WHERE username = ?",
		(username,),
	).fetchone()
	if existing:
		print("That username is already in use.")
		return

	conn.execute(
		"INSERT INTO user (admin, username, password) VALUES (?, ?, ?)",
		(False, username, _hash_password(password)),
	)
	conn.commit() # Save the new user to the database before confirming account creation.
	print(f"Account created for '{username}'.")


def _fetch_services(conn):
	"""Return all services ordered by name for consistent display."""
	return conn.execute(
		"SELECT id, name FROM service ORDER BY name"
	).fetchall()


def view_services(conn):
	"""Print the list of services currently in the system."""
	services = _fetch_services(conn)
	print("\nServices:")
	for service in services:
		print(f"{service['id']}. {service['name']}")


def _get_bus_model_ids(conn):
	"""Fetch and return a mapping from bus model name to bus model id."""
	rows = conn.execute("SELECT id, name FROM bus_model").fetchall()
	return {row["name"]: row["id"] for row in rows}


def create_service(conn):
	"""Create a service and generate buses and seven dated runs for it."""
	service_name = input("Enter new service name: ").strip()
	if not service_name:
		print("Service name is required.")
		return

	existing = conn.execute(
		"SELECT id FROM service WHERE name = ?",
		(service_name,),
	).fetchone()
	if existing:
		print("That service already exists.")
		return

	conn.execute("INSERT INTO service (name) VALUES (?)", (service_name,))
	# Get the id of the service we just inserted.
	service_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

	# To create buses for the new service, we need to know the bus model IDs for models A and B. We can fetch all bus models and build a mapping from name to ID. If either model is missing, we cannot proceed with creating the service.
	model_ids = _get_bus_model_ids(conn)
	model_a_id = model_ids.get(MODEL_A_NAME)
	model_b_id = model_ids.get(MODEL_B_NAME)
	if model_a_id is None or model_b_id is None:
		conn.rollback() # Undo the service insertion since we can't create the required buses.
		print(f"Cannot create service because bus models {MODEL_A_NAME} and {MODEL_B_NAME} are missing.")
		return

	conn.execute(
		"INSERT INTO bus (service_id, bus_model_id, runs_on) VALUES (?, ?, ?)",
		(service_id, model_a_id, RUNS_ON_WEEKEND),
	)
	weekend_bus_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

	conn.execute(
		"INSERT INTO bus (service_id, bus_model_id, runs_on) VALUES (?, ?, ?)",
		(service_id, model_b_id, RUNS_ON_WORKDAY),
	)
	workday_bus_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

	# Create seven runs for the new service, starting from today. Weekend runs use the model A bus, and weekday runs use the model B bus.
	today = datetime.now().date()
	for day_offset in range(RUNS_CREATED_PER_SERVICE):
		run_date = today + timedelta(days=day_offset)
		# Weekend runs use model A bus; weekdays use model B bus.
		bus_id = weekend_bus_id if run_date.weekday() >= 5 else workday_bus_id
		conn.execute(
			"INSERT INTO run (service_id, date, bus_id) VALUES (?, ?, ?)",
			(service_id, run_date.strftime("%Y-%m-%d"), bus_id),
		)

	conn.commit()
	print(f"Service '{service_name}' created")


def _fetch_future_runs(conn):
	"""Return future runs with related service and seat-capacity details."""
	today_str = datetime.now().strftime("%Y-%m-%d")
	return conn.execute(
		"""
		SELECT
			r.id,
			r.date,
			s.name AS service_name,
			bm.seats AS seats,
			COALESCE(SUM(t.number), 0) AS sold
		FROM run r
		JOIN service s ON s.id = r.service_id
		JOIN bus b ON b.id = r.bus_id
		JOIN bus_model bm ON bm.id = b.bus_model_id
		LEFT JOIN ticket t ON t.run_id = r.id
		WHERE r.date >= ?
		GROUP BY r.id, r.date, s.name, bm.seats
		ORDER BY s.name, r.date, r.id
		""",
		(today_str,),
	).fetchall()


def view_future_runs(conn):
	"""Display all future runs and their current remaining seat counts."""
	runs = _fetch_future_runs(conn)
	print("\nFuture bus runs:")
	if not runs:
		print("No runs available.")
		return

	for idx, run in enumerate(runs, start=1):
		available = run["seats"] - run["sold"]
		print(
			f"{idx}. {run['service_name']} | {run['date']} | "
			f"available seats: {available}"
		)


def buy_tickets(conn, user_id):
	"""Guide a customer through selecting a run and buying tickets."""
	runs = _fetch_future_runs(conn)
	if not runs:
		print("No runs available.")
		return

	print("\nChoose a run:")
	for idx, run in enumerate(runs, start=1):
		# Available seats = bus capacity - tickets already sold.
		available = run["seats"] - run["sold"]
		print(f"{idx}. {run['service_name']} | {run['date']} | available: {available}")

	try:
		run_choice = int(input("Run number: ").strip())
	except ValueError:
		print("Invalid run number.")
		return

	if run_choice < 1 or run_choice > len(runs):
		print("Invalid run number.")
		return

	selected_run = runs[run_choice - 1] # Adjust for 0-based index

	try:
		quantity = int(input("Number of tickets: ").strip())
	except ValueError:
		print("Invalid number of tickets.")
		return

	if quantity <= 0:
		print("Number of tickets must be positive.")
		return

	available = selected_run["seats"] - selected_run["sold"] # Recalculate available seats in case something changed since we displayed the list.
	if quantity > available:
		print("Not enough seats available.")
		return

	# Match the original assignment flow: Enter confirms, 'esc' cancels.
	confirmation = input("Press Enter to confirm booking or type 'esc' to cancel: ").strip().lower()
	if confirmation == "esc":
		print("Booking cancelled.")
		return

	conn.execute(
		"INSERT INTO ticket (user_id, run_id, number) VALUES (?, ?, ?)",
		(user_id, selected_run["id"], quantity),
	)
	conn.commit()
	print("Booking confirmed!")


def view_my_tickets(conn, user_id):
	"""Display all tickets purchased by the given user."""
	rows = conn.execute(
		"""
		SELECT t.id, t.number, r.date, s.name AS service_name
		FROM ticket t
		JOIN run r ON r.id = t.run_id
		JOIN service s ON s.id = r.service_id
		WHERE t.user_id = ?
		ORDER BY t.id
		""",
		(user_id,),
	).fetchall()

	print("\nMy tickets:")
	if not rows:
		print("No tickets purchased yet.")
		return

	for row in rows:
		print(f"#{row['id']}: {row['service_name']} on {row['date']} x {row['number']}")

# === Menu loops for admin and customer users ===
def admin_menu(conn):
	"""Run the menu loop for an authenticated admin user."""
	while True:
		print("\nAdmin menu")
		print("1. View services")
		print("2. Create a service")
		print("3. Log out")

		choice = _prompt_menu_choice("Choose an option: ", {"1", "2", "3"})
		if choice == "1":
			view_services(conn)
		elif choice == "2":
			create_service(conn)
		else:
			break


def customer_menu(conn, user):
	"""Run the menu loop for an authenticated ordinary user."""
	while True:
		print("\nCustomer menu")
		print("1. View future bus runs")
		print("2. Buy tickets")
		print("3. View my tickets")
		print("4. Log out")

		choice = _prompt_menu_choice("Choose an option: ", {"1", "2", "3", "4"})
		if choice == "1":
			view_future_runs(conn)
		elif choice == "2":
			buy_tickets(conn, user["id"])
		elif choice == "3":
			view_my_tickets(conn, user["id"])
		else:
			break

# Main entry point to start the booking system and run the home menu loop.
# Stayed the same till the end. Same with most of the menu and booking logic as it was already well-structured.
def main():
	"""Start the booking system and run the home menu loop."""
	if not DB_PATH.exists():
		create_database()

	conn = _connect()
	try:
		while True:
			print("\n=== Transport Booking System ===")
			print("1. Log in")
			print("2. Create an account")
			print("3. Exit")

			choice = _prompt_menu_choice("Choose an option: ", {"1", "2", "3"})

			if choice == "1":
				user = login(conn)
				if not user: # Login failed, return to main menu.
					continue
				if user["admin"]:
					admin_menu(conn)
				else:
					customer_menu(conn, user)
			elif choice == "2":
				create_account(conn)
			else:
				print("Goodbye.")
				break
	finally:
		conn.close()


if __name__ == "__main__":
	main()

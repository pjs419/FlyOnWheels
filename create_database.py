"""Create and seed the FlyOnWheels SQLite database."""

import hashlib # For hashing passwords securely
import sqlite3 # For interacting with the SQLite database
from datetime import datetime, timedelta # For handling dates when creating runs
from pathlib import Path # For constructing the database file path

# Import data model classes for structured data handling
from bus import Bus
from bus_model import BusModel
from run import Run
from service import Service
from ticket import Ticket
from user import User

DB_PATH = Path(__file__).resolve().parent / 'flyonwheels.db' # Database file path in the same directory as this script
# Changed from a hardcoded string to a Path object for better path handling across different operating systems and to leverage Path's convenient methods for file operations. Wouldve been more error-prone to use a string path directly, especially if we wanted to make this script more flexible in the future

# Constant defining how many days ahead to create runs for when seeding the database
RUN_DAYS_AHEAD = 7
BUS_WEEKEND = 'weekend'
BUS_WORKDAY = 'workday'

# === HELPER FUNCTIONS FOR DATA INSERTION LOGIC ===
# Another change was to break down the data insertion logic into separate helper functions for each type of data (users, bus models, services, buses, runs, and tickets). This improves code organization and readability by giving each function a single responsibility and making it easier to understand the flow of data insertion in the main create_database function. It also allows for easier testing and maintenance of each individual data insertion step in isolation if needed.
def _insert_default_admin(cursor):
    """Insert the initial admin account."""
    password_hash = hashlib.sha256('pqr123#!'.encode('utf-8')).hexdigest()
    admin_user = User(id=None, admin=True, username='Bob', password=password_hash)
    cursor.execute(
        'INSERT INTO user (admin, username, password) VALUES (?, ?, ?)',
        (admin_user.admin, admin_user.username, admin_user.password),
    )
    admin_user.id = cursor.lastrowid # Update the user object with the generated ID from the database
    #lastrowid is a property of the cursor that gives the ID of the last inserted row, which we use to update our User object with its assigned ID from the database.
    return admin_user


def _insert_default_bus_models(cursor):
    """Insert default bus models and return a mapping of model name to model object."""
    models_by_name = {}
    bus_models = [ 
        BusModel(id=None, name='A', seats=30),
        BusModel(id=None, name='B', seats=50),
    ]
    for model in bus_models:
        cursor.execute(
            'INSERT INTO bus_model (name, seats) VALUES (?, ?)',
            (model.name, model.seats),
        )
        model.id = cursor.lastrowid # Update the model object with the generated ID from the database
        models_by_name[model.name] = model # Store the model in a dictionary for easy lookup by name later when creating buses
    return models_by_name


def _insert_default_services(cursor):
    """Insert default services and return created service objects."""
    services = [
        Service(id=None, name='Dublin to Kilkenny, 7pm'),
        Service(id=None, name='Dublin to Letterkenny, 8am'),
        Service(id=None, name='Dublin to Wicklow, 6pm'),
    ]
    for service in services:
        cursor.execute('INSERT INTO service (name) VALUES (?)', (service.name,))
        service.id = cursor.lastrowid # Update the service object with the generated ID from the database
    return services


def _insert_buses_for_services(cursor, services, models_by_name):
    """Insert weekend/workday buses per service and return service-to-bus-object mapping."""
    service_bus_map = {}
    for service in services:
        weekend_bus = Bus(
            id=None,
            service_id=service.id,
            bus_model_id=models_by_name['A'].id,
            runs_on=BUS_WEEKEND,
        )
        cursor.execute(
            'INSERT INTO bus (service_id, bus_model_id, runs_on) VALUES (?, ?, ?)',
            (weekend_bus.service_id, weekend_bus.bus_model_id, weekend_bus.runs_on),
        )
        weekend_bus.id = cursor.lastrowid # Update the bus object with the generated ID from the database

        workday_bus = Bus(
            id=None,
            service_id=service.id,
            bus_model_id=models_by_name['B'].id,
            runs_on=BUS_WORKDAY,
        )
        cursor.execute(
            'INSERT INTO bus (service_id, bus_model_id, runs_on) VALUES (?, ?, ?)',
            (workday_bus.service_id, workday_bus.bus_model_id, workday_bus.runs_on),
        )
        workday_bus.id = cursor.lastrowid # Update the bus object with the generated ID from the database

        service_bus_map[service.id] = {
            BUS_WEEKEND: weekend_bus,
            BUS_WORKDAY: workday_bus,
        } # Store the created buses in a mapping keyed by service ID for later use when creating runs
    return service_bus_map


def _insert_runs(cursor, service_bus_map):
    """Insert runs for each service for the configured date horizon."""
    created_runs = []
    today = datetime.now().date()
    for service_id, buses in service_bus_map.items(): # Iterate through each service and its associated buses to create runs for the next RUN_DAYS_AHEAD days
        for day_offset in range(RUN_DAYS_AHEAD): # For each day offset from today, calculate the run date and determine which bus to use based on whether it's a weekend or workday, then insert a run into the database
            run_date = today + timedelta(days=day_offset)
            runs_on = BUS_WEEKEND if run_date.weekday() >= 5 else BUS_WORKDAY
            run = Run(
                id=None,
                service_id=service_id,
                date=run_date.strftime('%Y-%m-%d'),
                bus_id=buses[runs_on].id,
            )
            cursor.execute(
                'INSERT INTO run (service_id, date, bus_id) VALUES (?, ?, ?)',
                (run.service_id, run.date, run.bus_id),
            )
            run.id = cursor.lastrowid # Update the run object with the generated ID from the database
            created_runs.append(run) # Keep track of created runs in a list in case we want to use this information later (e.g., for creating tickets or verifying data)
    return created_runs


def _insert_initial_ticket(cursor, user, service):
    """Insert a sample ticket for Bob for the given service on the next day."""
    next_day = (datetime.now().date() + timedelta(days=1)).strftime('%Y-%m-%d')
    cursor.execute('SELECT id FROM run WHERE service_id = ? AND date = ?', (service.id, next_day))
    run_row = cursor.fetchone() # Fetch the run for the given service on the next day to associate the ticket with. If no such run exists, we won't create a ticket.
    if run_row is None: # If there is no run for the given service on the next day, we cannot create a ticket, so we simply
        return
    starter_ticket = Ticket(id=None, user_id=user.id, run_id=run_row[0], number=1)
    cursor.execute(
        'INSERT INTO ticket (user_id, run_id, number) VALUES (?, ?, ?)',
        (starter_ticket.user_id, starter_ticket.run_id, starter_ticket.number),
    )
    starter_ticket.id = cursor.lastrowid # Update the ticket object with the generated ID from the database
    return starter_ticket

# === MAIN DATABASE CREATION FUNCTION ===
# This function stayed true to the original version. Only change was using DB_PATH as a Path object instead of a string, which required using the .exists() and .unlink() methods to check for and delete the existing database file if it exists before creating a new one. The rest of the logic for creating tables and inserting data remained the same, just organized into helper functions for better readability and maintainability.
def create_database():
    """Create the database file, schema, and seed data used by week10 exercises."""
    # Recreate database from scratch each time to avoid duplicate rows.
    if DB_PATH.exists():
        DB_PATH.unlink()

    # Connect to SQLite database (creates file if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # ===== TABLE CREATION =====
    # Create User table (stores system users and admin information)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY,
            admin BOOLEAN,
            username TEXT,
            password TEXT
        )
    ''')
    
    # Create BusModel table (defines bus types with their capacities)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bus_model (
            id INTEGER PRIMARY KEY,
            name TEXT,
            seats INTEGER
        )
    ''')
    
    # Create Service table (bus routes and schedules)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS service (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    ''')
    
    # Create Bus table (physical bus instances assigned to services)
    # Links a service to a bus model and specifies which days it operates
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bus (
            id INTEGER PRIMARY KEY,
            service_id INTEGER,
            bus_model_id INTEGER,
            runs_on TEXT,
            FOREIGN KEY(service_id) REFERENCES service(id),
            FOREIGN KEY(bus_model_id) REFERENCES bus_model(id)
        )
    ''')
    
    # Create Run table (scheduled bus runs on specific dates)
    # Represents a service operating on a particular day with a specific bus
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS run (
            id INTEGER PRIMARY KEY,
            service_id INTEGER,
            date TEXT,
            bus_id INTEGER,
            FOREIGN KEY(service_id) REFERENCES service(id),
            FOREIGN KEY(bus_id) REFERENCES bus(id)
        )
    ''')
    
    # Create Ticket table (user bookings for bus runs)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            run_id INTEGER,
            number INTEGER,
            FOREIGN KEY(user_id) REFERENCES user(id),
            FOREIGN KEY(run_id) REFERENCES run(id)
        )
    ''')
    
    # === DATA INSERTION ===
    # Old data insertion approach were mostly done directly in create_database, but to improve code organization and readability, we refactored the data insertion logic into separate helper functions for each type of data (users, bus models, services, buses, runs, and tickets). This way, the main create_database function is cleaner and each helper function has a single responsibility, making it easier to understand and maintain.
    #Was harder to see or test one insert step in isolation.

    # Insert default admin user, bus models, services, buses for each service, and runs for each bus. We also create a sample ticket for the admin user for one of the services to have some initial data in the system.
    admin_user = _insert_default_admin(cursor)
    models_by_name = _insert_default_bus_models(cursor)
    services = _insert_default_services(cursor)
    service_bus_map = _insert_buses_for_services(cursor, services, models_by_name)
    _insert_runs(cursor, service_bus_map)

    # Bob gets one starter ticket for the second default service.
    _insert_initial_ticket(cursor, admin_user, services[1])
    
    # Commit all changes to the database and close the connection
    conn.commit()
    conn.close()
    # Print confirmation message
    print("Database 'flyonwheels.db' created successfully!")


# Run the script only if executed directly (not imported as a module)
if __name__ == '__main__':
    create_database()

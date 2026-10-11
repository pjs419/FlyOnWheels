"""Utility script to print FlyOnWheels database schema and data."""

# Import SQLite library for database operations
import sqlite3

from create_database import DB_PATH

# Function to open and display all database tables and their contents
def test_database():
    """Opens the flyonwheels.db database and dumps all tables with their data."""
    # Connect to the existing flyonwheels database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Retrieve all table names from the database
    # This query gets all table names from SQLite's internal schema
    cursor.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    tables = cursor.fetchall()
    
    # Print header for the output
    print("=== Database Tables ===")
    print("\nThis output shows all tables in the flyonwheels database with their schemas and data.\n")
    
    # Iterate through each table and display its structure and contents
    for table in tables:
        table_name = table[0]  # Extract table name from tuple
        print(f"\n--- Table: {table_name} ---")
        
        # Get column information (PRAGMA returns column metadata)
        # Returns: (id, name, type, notnull, dflt_value, pk)
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        # Extract column names from the metadata
        # columns[1] contains the column name from each PRAGMA result
        column_names = [col[1] for col in columns]
        # Display the column names for this table
        print("Columns: " + ", ".join(column_names))
        
        # Query all rows from the current table
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        # Display the number of records in this table
        print(f"Records: {len(rows)}")
        # Display each row of data
        for row in rows:
            print(row)
    
    # Close the database connection
    conn.close()


# Run the test function only if this script is executed directly
if __name__ == '__main__':
    test_database()

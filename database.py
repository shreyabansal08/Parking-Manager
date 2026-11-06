"""
ParkEase - shared database layer (Person 4).

Other team members should only IMPORT functions from this file:

    from database import init_db, get_available_spots, insert_vehicle

They never need to write SQL themselves.

Return conventions
------------------
* Search functions return a dict (one record), None (not found) or a list of dicts.
* Insert/update functions return a dict: {"success": True/False, "message": "..."}.
  (Sometimes with extra keys such as "vehicle" or "spot".)
* Unexpected database problems (e.g. file locked, disk error) are NOT hidden:
  the sqlite3.Error is raised so it is visible and can be fixed.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "parkease.db"       # the real project database
SCHEMA_PATH = BASE_DIR / "schema.sql"    # table definitions

SAMPLE_SPOT_IDS = [f"P{number:02d}" for number in range(1, 11)]   # P01 ... P10
VALID_STATUSES = ("available", "occupied")
VALID_VEHICLE_TYPES = ("car", "bike", "other")


# ---------------------------------------------------------------------------
# Connection handling
# ---------------------------------------------------------------------------
@contextmanager
def get_connection(db_path=DB_PATH):
    """Open a connection, commit if everything worked, roll back on error, always close."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row           # lets us read columns by name
    connection.execute("PRAGMA foreign_keys = ON")  # SQLite has this OFF by default!
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise                                       # never hide the error
    finally:
        connection.close()


def _clean(value):
    """Strip spaces and make upper case so 'p01 ' and 'P01' are treated the same."""
    return value.strip().upper() if isinstance(value, str) else ""


def _result(success, message, **extra):
    """Build the standard {"success", "message"} reply used by all write functions."""
    return {"success": success, "message": message, **extra}


def _row_to_dict(row):
    return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------
def init_db(db_path=DB_PATH):
    """Create the tables (if missing) and add sample spots P01-P10 (if missing).
    Safe to call every time the app starts."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection(db_path) as conn:
        conn.executescript(schema_sql)
        # INSERT OR IGNORE skips spots that already exist -> no duplicates.
        conn.executemany(
            "INSERT OR IGNORE INTO parking_spots (spot_id) VALUES (?)",
            [(spot_id,) for spot_id in SAMPLE_SPOT_IDS],
        )


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------
def insert_parking_spot(spot_id, db_path=DB_PATH):
    """Add a new parking spot (status starts as 'available')."""
    spot_id = _clean(spot_id)
    if not spot_id:
        return _result(False, "Spot ID cannot be empty.")
    try:
        with get_connection(db_path) as conn:
            conn.execute("INSERT INTO parking_spots (spot_id) VALUES (?)", (spot_id,))
    except sqlite3.IntegrityError:
        return _result(False, f"Parking spot {spot_id} already exists.")
    return _result(True, f"Parking spot {spot_id} added.", spot=get_parking_spot(spot_id, db_path))


def insert_vehicle(registration_number, owner_name, vehicle_type="car", db_path=DB_PATH):
    """Register a new vehicle (not parked yet). Duplicate registration numbers are rejected."""
    registration_number = _clean(registration_number)
    owner_name = owner_name.strip() if isinstance(owner_name, str) else ""
    vehicle_type = vehicle_type.strip().lower() if isinstance(vehicle_type, str) else ""

    if not registration_number:
        return _result(False, "Registration number cannot be empty.")
    if not owner_name:
        return _result(False, "Owner name cannot be empty.")
    if vehicle_type not in VALID_VEHICLE_TYPES:
        return _result(False, f"Vehicle type must be one of: {', '.join(VALID_VEHICLE_TYPES)}.")

    try:
        with get_connection(db_path) as conn:
            conn.execute(
                "INSERT INTO vehicles (registration_number, owner_name, vehicle_type) VALUES (?, ?, ?)",
                (registration_number, owner_name, vehicle_type),
            )
    except sqlite3.IntegrityError:
        return _result(False, f"Vehicle {registration_number} is already registered.")
    return _result(True, f"Vehicle {registration_number} registered.",
                   vehicle=get_vehicle(registration_number, db_path))


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def get_parking_spot(spot_id, db_path=DB_PATH):
    """Return the spot as a dict, or None if it does not exist."""
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM parking_spots WHERE spot_id = ?",
                           (_clean(spot_id),)).fetchone()
    return _row_to_dict(row)


def get_vehicle(registration_number, db_path=DB_PATH):
    """Return the vehicle as a dict, or None if it does not exist."""
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM vehicles WHERE registration_number = ?",
                           (_clean(registration_number),)).fetchone()
    return _row_to_dict(row)


def get_all_vehicles(db_path=DB_PATH):
    """Return every registered vehicle as a list of dicts (extra helper)."""
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM vehicles ORDER BY registration_number").fetchall()
    return [dict(row) for row in rows]


def get_all_spots(db_path=DB_PATH):
    """Return all parking spots as a list of dicts."""
    return _get_spots(None, db_path)


def get_available_spots(db_path=DB_PATH):
    """Return only spots whose status is 'available'."""
    return _get_spots("available", db_path)


def get_occupied_spots(db_path=DB_PATH):
    """Return only spots whose status is 'occupied'."""
    return _get_spots("occupied", db_path)


def _get_spots(status, db_path):
    sql = "SELECT * FROM parking_spots"
    params = ()
    if status is not None:
        sql += " WHERE status = ?"
        params = (status,)
    with get_connection(db_path) as conn:
        rows = conn.execute(sql + " ORDER BY spot_id", params).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
def update_spot_status(spot_id, status, db_path=DB_PATH):
    """Manually change a spot's status ('available' or 'occupied').
    A spot that currently holds a vehicle cannot be set to 'available' - use release_spot()."""
    spot_id = _clean(spot_id)
    status = status.strip().lower() if isinstance(status, str) else ""
    if status not in VALID_STATUSES:
        return _result(False, f"Status must be one of: {', '.join(VALID_STATUSES)}.")

    with get_connection(db_path) as conn:
        if conn.execute("SELECT 1 FROM parking_spots WHERE spot_id = ?", (spot_id,)).fetchone() is None:
            return _result(False, f"Parking spot {spot_id} does not exist.")
        if status == "available":
            parked = conn.execute("SELECT registration_number FROM vehicles WHERE spot_id = ?",
                                  (spot_id,)).fetchone()
            if parked is not None:
                return _result(False, f"Spot {spot_id} holds vehicle {parked['registration_number']}; "
                                      "use release_spot() instead.")
        conn.execute("UPDATE parking_spots SET status = ? WHERE spot_id = ?", (status, spot_id))
    return _result(True, f"Spot {spot_id} is now {status}.", spot=get_parking_spot(spot_id, db_path))


def assign_vehicle_to_spot(registration_number, spot_id, db_path=DB_PATH):
    """Park a registered vehicle in an available spot.
    Both changes (spot -> occupied, vehicle -> spot) happen together or not at all."""
    registration_number = _clean(registration_number)
    spot_id = _clean(spot_id)

    with get_connection(db_path) as conn:
        vehicle = conn.execute("SELECT * FROM vehicles WHERE registration_number = ?",
                               (registration_number,)).fetchone()
        if vehicle is None:
            return _result(False, f"Vehicle {registration_number} is not registered.")
        if vehicle["spot_id"] is not None:
            return _result(False, f"Vehicle {registration_number} is already parked in {vehicle['spot_id']}.")
        if conn.execute("SELECT 1 FROM parking_spots WHERE spot_id = ?", (spot_id,)).fetchone() is None:
            return _result(False, f"Parking spot {spot_id} does not exist.")

        # The WHERE status='available' makes this check-and-update a single step.
        changed = conn.execute(
            "UPDATE parking_spots SET status = 'occupied' WHERE spot_id = ? AND status = 'available'",
            (spot_id,),
        ).rowcount
        if changed == 0:
            return _result(False, f"Parking spot {spot_id} is already occupied.")

        conn.execute(
            "UPDATE vehicles SET spot_id = ?, assigned_at = ? WHERE vehicle_id = ?",
            (spot_id, datetime.now().isoformat(timespec="seconds"), vehicle["vehicle_id"]),
        )
    return _result(True, f"Vehicle {registration_number} parked in {spot_id}.",
                   vehicle=get_vehicle(registration_number, db_path),
                   spot=get_parking_spot(spot_id, db_path))


def release_spot(spot_id, db_path=DB_PATH):
    """Free a spot: the vehicle stays registered but is no longer parked."""
    spot_id = _clean(spot_id)
    with get_connection(db_path) as conn:
        spot = conn.execute("SELECT * FROM parking_spots WHERE spot_id = ?", (spot_id,)).fetchone()
        if spot is None:
            return _result(False, f"Parking spot {spot_id} does not exist.")
        if spot["status"] == "available":
            return _result(False, f"Parking spot {spot_id} is already available.")

        vehicle = conn.execute("SELECT registration_number FROM vehicles WHERE spot_id = ?",
                               (spot_id,)).fetchone()
        conn.execute("UPDATE vehicles SET spot_id = NULL, assigned_at = NULL WHERE spot_id = ?", (spot_id,))
        conn.execute("UPDATE parking_spots SET status = 'available' WHERE spot_id = ?", (spot_id,))

    released = vehicle["registration_number"] if vehicle else None
    return _result(True, f"Spot {spot_id} released.", released_vehicle=released,
                   spot=get_parking_spot(spot_id, db_path))


def update_vehicle(registration_number, owner_name=None, vehicle_type=None, db_path=DB_PATH):
    """Change a vehicle's owner name and/or type. Leave an argument as None to keep it unchanged.
    (The registration number itself is the identifier and is not changed here.)"""
    registration_number = _clean(registration_number)
    if owner_name is None and vehicle_type is None:
        return _result(False, "Nothing to update.")

    vehicle = get_vehicle(registration_number, db_path)
    if vehicle is None:
        return _result(False, f"Vehicle {registration_number} is not registered.")

    new_owner = vehicle["owner_name"] if owner_name is None else owner_name.strip()
    new_type = vehicle["vehicle_type"] if vehicle_type is None else vehicle_type.strip().lower()
    if not new_owner:
        return _result(False, "Owner name cannot be empty.")
    if new_type not in VALID_VEHICLE_TYPES:
        return _result(False, f"Vehicle type must be one of: {', '.join(VALID_VEHICLE_TYPES)}.")

    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE vehicles SET owner_name = ?, vehicle_type = ? WHERE registration_number = ?",
            (new_owner, new_type, registration_number),
        )
    return _result(True, f"Vehicle {registration_number} updated.",
                   vehicle=get_vehicle(registration_number, db_path))


if __name__ == "__main__":
    init_db()
    print(f"Database ready at {DB_PATH} with {len(get_all_spots())} parking spots.")

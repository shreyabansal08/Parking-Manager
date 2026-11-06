-- ParkEase database schema (Person 4)
-- Safe to run many times: every statement uses IF NOT EXISTS.

-- Table 1: parking spots -------------------------------------------------
CREATE TABLE IF NOT EXISTS parking_spots (
    -- Human-readable ID such as 'P01'. It is the primary key, so no two spots can share it.
    spot_id TEXT PRIMARY KEY
        CHECK (length(trim(spot_id)) > 0),

    -- Only two legal values; anything else is rejected by the database itself.
    status TEXT NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'occupied'))
);

-- Table 2: vehicles ------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehicles (
    -- Internal number generated automatically (1, 2, 3, ...).
    vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Number plate. UNIQUE = the same vehicle cannot be registered twice.
    registration_number TEXT NOT NULL UNIQUE
        CHECK (length(trim(registration_number)) > 0),

    owner_name TEXT NOT NULL
        CHECK (length(trim(owner_name)) > 0),

    vehicle_type TEXT NOT NULL DEFAULT 'car'
        CHECK (vehicle_type IN ('car', 'bike', 'other')),

    -- Which spot the vehicle is parked in. NULL = not parked right now.
    -- FOREIGN KEY: must match an existing parking_spots.spot_id.
    -- UNIQUE: one spot can belong to at most one vehicle (NULLs are allowed many times).
    spot_id TEXT UNIQUE,

    -- When the vehicle was assigned to its spot (NULL when not parked).
    assigned_at TEXT,

    FOREIGN KEY (spot_id) REFERENCES parking_spots (spot_id)
);

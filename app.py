import os
from flask import Flask, render_template, request, jsonify
import database

app = Flask(__name__)

# Initialize database if it doesn't exist yet
if not os.path.exists(database.DB_NAME):
    database.init_db()

# --- Person 1 & 4: Dashboard Route ---
@app.route("/")
def index():
    spots = database.get_all_spots()
    counts = database.get_counts()
    return render_template("index.html", spots=spots, counts=counts)

@app.route("/api/spots", methods=["GET"])
def api_spots():
    return jsonify({
        "spots": database.get_all_spots(),
        "counts": database.get_counts()
    })

# --- Person 2: Parking Management Routes ---
@app.route("/api/occupy/<int:spot_id>", methods=["POST"])
def occupy_spot(spot_id):
    success, message = database.set_spot_status(spot_id, occupy=True)
    status_code = 200 if success else 400
    return jsonify({
        "success": success,
        "message": message,
        "spots": database.get_all_spots(),
        "counts": database.get_counts()
    }), status_code

@app.route("/api/release/<int:spot_id>", methods=["POST"])
def release_spot(spot_id):
    success, message = database.set_spot_status(spot_id, occupy=False)
    status_code = 200 if success else 400
    return jsonify({
        "success": success,
        "message": message,
        "spots": database.get_all_spots(),
        "counts": database.get_counts()
    }), status_code

# --- Person 3: Vehicle Registration & Search Routes ---
@app.route("/register", methods=["GET", "POST"])
def register():
    message = None
    success = None
    if request.method == "POST":
        reg_number = request.form.get("reg_number", "").strip()
        owner_name = request.form.get("owner_name", "").strip()
        
        if not reg_number or not owner_name:
            success = False
            message = "Both registration number and owner's name are required."
        else:
            success, message = database.register_vehicle(reg_number, owner_name)
            
    return render_template("register.html", message=message, success=success)

@app.route("/search", methods=["GET", "POST"])
def search():
    vehicle = None
    searched = False
    query = ""
    if request.method == "POST":
        searched = True
        query = request.form.get("reg_number", "").strip()
        if query:
            vehicle = database.search_vehicle(query)
            
    return render_template("search.html", vehicle=vehicle, searched=searched, query=query)

if __name__ == "__main__":
    app.run(debug=True)

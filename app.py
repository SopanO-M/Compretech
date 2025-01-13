import os
from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
from haversine import haversine, Unit
from pymongo import MongoClient, DESCENDING
from bson import ObjectId
import json
from datetime import datetime, timedelta
import logging
from flask import current_app
from functools import wraps

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Add this custom JSON encoder to handle ObjectI


app = Flask(__name__)

# MongoDB setup
mongo_uri = os.getenv("MONGO_URI") 
client = MongoClient(mongo_uri) 
db = client['attendance_system']
punch_collection = db['punch_records']


# Geofence center and radius
geofence_center = (22.27174507140292, 73.17586006441583)  # Example coordinates
geofence_radius = 1000000  # 1000 meters radius

users = {
    "u_Nirav": "19581",
    "u_Vikram": "18493",
    "u_Mitesh": "17026",
    "u_Test": "2024",
    "admin": "Kal180" ,
}

# Predefined users and their credentials (username, password)



logged_in_user = None

class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

def get_time_with_offset():
    """Returns the current time with a +5:30 offset (IST)."""
    current_time = datetime.utcnow()  # Get current UTC time
    offset = timedelta(hours=5, minutes=30)  # IST offset
    ist_time = current_time + offset
    return ist_time

def get_user_last_punch(username):
    """Get the last punch record for a specific user"""
    last_punch = punch_collection.find_one(
        {"username": username},
        sort=[("timestamp", -1)]
    )
    
    # Check if last punch was more than 36 hours ago
    if last_punch:
        current_time = get_time_with_offset()
        time_difference = current_time - last_punch['timestamp']
        if time_difference.total_seconds() > (36 * 3600):  # 36 hours in seconds
            return None  # This will reset to Punch In state
    
    return last_punch

def calculate_work_duration(punch_in_time, punch_out_time):
    """Calculate duration between punch in and punch out"""
    if not punch_in_time or not punch_out_time:
        return None
    
    duration = punch_out_time - punch_in_time
    hours = duration.total_seconds() / 3600
    return round(hours, 2)



# Haversine formula to calculate distance
def calculate_distance(user_location):
    try:
        if not isinstance(user_location, tuple) or len(user_location) != 2:
            logger.error(f"Invalid location format: {user_location}")
            return float('inf')
        
        lat, lng = user_location
        if not (isinstance(lat, (int, float)) and isinstance(lng, (int, float))):
            logger.error(f"Invalid coordinate types: lat={type(lat)}, lng={type(lng)}")
            return float('inf')
            
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            logger.error(f"Coordinates out of range: lat={lat}, lng={lng}")
            return float('inf')
            
        return haversine(user_location, geofence_center, unit=Unit.METERS)
    except Exception as e:
        logger.error(f"Distance calculation error: {str(e)}")
        return float('inf')
    
# HTML Login Page
LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
    <style>
        body {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #ff7eb3, #ff758c, #fdb15c, #ffde59, #a7ff83, #17c3b2, #2d6cdf, #7c5cdb);
            background-size: 300% 300%;
            animation: gradientBG 10s ease infinite;
            color: #ffffff;
        }

        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        .container {
            max-width: 400px;
            width: 100%; /* Ensures responsiveness */
            background : linear-gradient(135deg, #30343F, #404452);
            margin: 20px auto;
            padding: 30px;
            border-radius: 25px;
            box-shadow: 0 8px 15px rgba(0, 0, 0, 0.3); /* Adds depth */
            color: white;
            min-height : 400px
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            font-size: 16px;
        }
      
        h1, h2 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5rem;
        }
        .form-group {
            margin-bottom: 15px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
            color: white
        }

        select, input {
            padding: 10px;
            width: 100%;
            margin-bottom: 18px;
            border-radius: 5px;
            border: 1px solid #ccc;
            font-size: 16px;
            box-sizing: border-box;
        }

        button {
            width: 100%;
            padding: 12px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 18px;
            transition: background-color 0.3s ease;
        }

        button:hover {
            background-color: orange;
        }

        .error {
            color: #dc3545;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            text-align: center;
        }

        .success {
            color: #28a745;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>Login</h2>
        <form method="POST">
            <label for="username">Select Username:</label>
            <select id="username" name="username" required>
                <option value="" selected disabled>Select User</option>
                <option value="u_Nirav">Nirav</option>
                <option value="u_Vikram">Vikram</option>
                <option value="u_Mitesh">Mitesh</option>
                <option value="u_Test">Test</option>
                <option value="admin">Admin</option>
            </select>
            
            <label for="password">Password:</label>
            <input type="password" id="password" name="password" required><br><br>
            
            <button type="submit">Login</button>
        </form>
        {% if error %}
        <p style="color: red;">{{ error }}</p>
        {% endif %}
    </div>
</body>
</html>

"""
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Attendance Punch System</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <script>
        setTimeout(function() {
            window.location.href = '/logout';
        }, 50000);
    </script>    
    <style>
        body {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #ff7eb3, #ff758c, #fdb15c, #ffde59, #a7ff83, #17c3b2, #2d6cdf, #7c5cdb);
            background-size: 300% 300%;
            animation: gradientBG 10s ease infinite;
            color: #ffffff;
        }

        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        .container {
            max-width: 700px;
            width: 100%; /* Ensures responsiveness */
            background : linear-gradient(135deg, #30343F, #404452);
            margin: 20px auto;
            padding: 30px;
            border-radius: 25px;
            box-shadow: 0 8px 15px rgba(0, 0, 0, 0.3); /* Adds depth */
            color: white;
            min-height : 400px
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            font-size: 16px;
        }
      
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5rem;
        }

        h2 {
            color: white;
            text-align: left;
            margin-bottom: 30px;
            font-size: 18px;
        }

        .form-group {
            margin-bottom: 15px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
            color: white
        }

        button {
            width: 100%;
            padding: 12px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 18px;
            transition: background-color 0.3s ease;
        }

        button:hover {
            background-color: orange;
        }

        .punch-circle {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            text-align: center;
            font-size: 1.2em;
            font-weight: bold;
            color: #fff;
            cursor: pointer;
            margin: 10px auto;
            line-height: 150px;
            position: relative;
        }
        .punch-in { background-color: #4CAF50; }
        .punch-out { background-color: #f44336; }
        .punch-circle:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        #geofence-status { margin-top: 20px; }
        #punch-history { margin-top: 20px; }
        #punch-history ul { list-style-type: none; }
        .remark-section { margin-bottom: 20px; }
        .remark-input {
            display : none;
            width: 100%;
            padding: 8px;
            margin-top: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        #user-coordinates {
            margin-top: 10px;
            font-weight: bold;
            color: #ff0000;
        }
        #map {
            display : none;
            width: 400px; /* Set the width of the map */
            height: 300px; /* Set the height of the map */
            margin: 0 auto; /* Center the map horizontally */
            border: 2px solid #333; /* Optional: Add a border for better visibility */
            border-radius: 8px; /* Optional: Round the corners */
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3); /* Optiona
        }
        @media (max-width: 768px) {
            body {
                animation: none; /* Disable background animation on smaller screens */
            }
        }
        
    </style>
</head>
<body>
    <div class="container">
    <header>
        <h1>Attendance Punch System</h1>
    </header>

    <main>


        <section id="geofence-status">
            <p>Geofence Status: <span id="geofence-indicator">Checking...</span></p>
            <p id="user-coordinates" style="display: none;">Your Location: <span id="coordinates"></span></p>
        </section>

        <section id="punch-controls">           
            <div id="punch-in" class="punch-circle punch-in" style="display: none;">Punch In</div>
            <div id="punch-out" class="punch-circle punch-out" style="display: none;">Punch Out</div>
            <div class="remark-section">                
                <input type="text" id="user-remark" class="remark-input" placeholder="Enter your remark">
            </div>
        </section>    

        <section id="punch-history">
            <h2>Punch History</h2>
            <ul id="history-list"></ul>
        </section>

        <div id="map"></div>        
        
        <form method="POST" action="/logout">
            <button type="submit">Logout</button>
        </form>           
    </main>

    <footer>
        <p>&copy; 2025 Attendance System</p>
    </footer>

    <script>
        let hasPunchedIn = {{ 'true' if initial_status == 'Punch In' else 'false' }};
        let isProcessing = false;
        let userMarker;
        
        // Initialize map
        const map = L.map('map').setView([22.27174507140292, 73.17586006441583], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        // Add geofence circle
        const geofenceCircle = L.circle([22.27174507140292, 73.17586006441583], {
            radius: 1000000,
            color: 'blue',
            fillColor: '#30f',
            fillOpacity: 0.1
        }).addTo(map);

        function updateButtonVisibility() {
            if (hasPunchedIn) {
                document.getElementById('punch-in').style.display = 'none';
                document.getElementById('punch-out').style.display = 'block';
            } else {
                document.getElementById('punch-in').style.display = 'block';
                document.getElementById('punch-out').style.display = 'none';
            }
        }

        function updateCoordinates(lat, lng) {
            const coordinatesElement = document.getElementById('coordinates');
            if (coordinatesElement) {
                coordinatesElement.innerText = `Lat: ${lat.toFixed(6)}, Lng: ${lng.toFixed(6)}`;
            }
        }

        // Update these settings in your geolocation code
        const locationOptions = {
            enableHighAccuracy: true,
            maximumAge: 5000,
            timeout: 30000
        };

        function updateGeofenceStatus() {
            if (navigator.geolocation) {
               navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const userLat = position.coords.latitude;
                        const userLng = position.coords.longitude;

                        // Update map marker
                        if (userMarker) {
                            userMarker.setLatLng([userLat, userLng]);
                        } else {
                            userMarker = L.marker([userLat, userLng]).addTo(map);
                            map.setView([userLat, userLng], 13);
                        }

                        fetch('/get_geofence_status', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ latitude: userLat, longitude: userLng })
                        })
                        .then(response => {
                            if (!response.ok) {
                                throw new Error(`HTTP error! status: ${response.status}`);
                            }
                            return response.json();
                        })
                        .then(data => {
                            if (data.status === 'error') {
                                throw new Error(data.message || 'Geofence check failed');
                            }
                    
                            const indicator = document.getElementById('geofence-indicator');
                            indicator.innerText = data.status;
                            indicator.style.color = data.status === 'Inside Geofence' ? '#4CAF50' : '#f44336';

                            if (data.status === 'Outside Geofence') {
                                updateCoordinates(userLat, userLng);
                                document.getElementById('user-coordinates').style.display = 'block';
                                document.getElementById('punch-in').style.display = 'none';
                                document.getElementById('punch-out').style.display = 'none';
                            } else {
                                document.getElementById('user-coordinates').style.display = 'none';
                                updateButtonVisibility();
                            }
                        })
                        .catch(error => {
                            console.error('Geofence Error:', error);
                            document.getElementById('geofence-indicator').innerText = 'Error: ' + error.message;
                            document.getElementById('geofence-indicator').style.color = '#f44336';
                        });
                    },
                    (error) => {
                        console.error('Geolocation Error:', error);
                        document.getElementById('geofence-indicator').innerText = 'Location Error: ' + error.message;
                        document.getElementById('geofence-indicator').style.color = '#f44336';
                    },
                    locationOptions
                );
            }
        }
        updateGeofenceStatus();
            const intervalId = setInterval(updateGeofenceStatus, 15000);
        document.getElementById('punch-in').addEventListener('click', () => {
            if (!isProcessing) handlePunchAction('Punch In');
        });

        document.getElementById('punch-out').addEventListener('click', () => {
            if (!isProcessing) handlePunchAction('Punch Out');
        });

        function handlePunchAction(action) {
            isProcessing = true;
            showStatusMessage("Your input is getting saved...");
            disableButtons();

            const userRemark = document.getElementById('user-remark').value;

            navigator.geolocation.getCurrentPosition((position) => {
                fetch('/punch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: action,
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        userRemark: userRemark
                    })
                })
                .then(response => response.json())
                .then(data => {
                    addPunchRecord(data.message);
                    hasPunchedIn = (action === 'Punch In');
                    updateButtonVisibility();
                    showStatusMessage("Your input is saved!");
                    setTimeout(() => {
                        isProcessing = false;
                        enableButtons();
                    }, 5000);
                });
            });
        }

        function addPunchRecord(record) {
            const listItem = document.createElement('li');
            listItem.textContent = record;
            document.getElementById('history-list').insertBefore(listItem, document.getElementById('history-list').firstChild);
        }

        function showStatusMessage(message) {
            const statusElement = document.createElement('p');
            statusElement.id = 'status-message';
            statusElement.textContent = message;
            document.body.appendChild(statusElement);

            setTimeout(() => {
                const existingStatusElement = document.getElementById('status-message');
                if (existingStatusElement) existingStatusElement.remove();
            }, 5000);
        }

        function disableButtons() {
            document.getElementById('punch-in').disabled = true;
            document.getElementById('punch-out').disabled = true;
        }

        function enableButtons() {
            document.getElementById('punch-in').disabled = false;
            document.getElementById('punch-out').disabled = false;
        }

        fetch('/last_punch_status')
            .then(response => response.json())
            .then(data => {
                if (data.action) {
                    addPunchRecord(`Last ${data.action} at ${data.timestamp}`);
                }
            });
    </script>
</body>
</html>
"""

ADMIN_MENU_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard - Menu</title>
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            max-width: 600px;
            width: 90%;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }
        h1 {
            margin: 0;
            color: #333;
        }
        .menu-options {
            display: grid;
            gap: 20px;
            margin-top: 30px;
        }
        .menu-button {
            padding: 20px;
            font-size: 18px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: left;
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: white;
        }
        .pending-button {
            background-color: #4CAF50;
        }
        .processed-button {
            background-color: #2196F3;
        }
        .menu-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .logout-btn {
            background-color: #dc3545;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .arrow {
            font-size: 24px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Admin Dashboard</h1>
            <form method="POST" action="/logout" style="margin: 0;">
                <button type="submit" class="logout-btn">Logout</button>
            </form>
        </div>
        <div class="menu-options">
            <a href="/admin/pending" style="text-decoration: none;">
                <button class="menu-button pending-button">
                    View Pending Records
                    <span class="arrow">→</span>
                </button>
            </a>
            <a href="/admin/processed" style="text-decoration: none;">
                <button class="menu-button processed-button">
                    View Processed Records
                    <span class="arrow">→</span>
                </button>
            </a>
        </div>
    </div>
</body>
</html>
"""

ADMIN_PENDING_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pending Records - Admin Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .button-group {
            display: flex;
            gap: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background-color: white;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .status-select {
            padding: 6px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 120px;
        }
        .save-btn {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        .back-btn {
            background-color: #6c757d;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
        }
        .logout-btn {
            background-color: #dc3545;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .filter-section {
            margin-bottom: 20px;
        }
        .filter-section select {
            margin-right: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Pending Records</h1>
            <div class="button-group">
                <a href="/admin" class="back-btn">Back to Menu</a>
                <form method="POST" action="/logout" style="margin: 0;">
                    <button type="submit" class="logout-btn">Logout</button>
                </form>
            </div>
        </div>

        <div class="filter-section">
            <select id="userFilter" onchange="filterRecords()">
                <option value="">All Users</option>
                <option value="u_Nirav">Nirav</option>
                <option value="u_Vikram">Vikram</option>
                <option value="u_Mitesh">Mitesh</option>
                <option value="u_Test">Test</option>
            </select>
            <select id="statusFilter" onchange="filterRecords()">
                <option value="">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
            </select>
        </div>        

        <table id="pendingTable">
            <thead>
                <tr>
                    <th>Username</th>
                    <th>Action</th>
                    <th>Date & Time</th>
                    <th>User Remark</th>
                    <th>Status</th>
                    <th>Work Duration (Hours)</th>
                    <th>Admin Remark</th>
                </tr>
            </thead>
            <tbody>
                {% for record in records %}
                <tr data-username="{{ record.username }}" data-status="{{ record.status }}">
                    <td>{{ record.username }}</td>
                    <td>{{ record.action }}</td>
                    <td>{{ record.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</td>
                    <td>{{ record.userRemark or '' }}</td>
                    <td>
                        <select class="status-select" data-record-id="{{ record._id }}">
                            <option value="pending" {% if record.status == 'pending' %}selected{% endif %}>Pending</option>
                            <option value="approved" {% if record.status == 'approved' %}selected{% endif %}>Approved</option>
                            <option value="rejected" {% if record.status == 'rejected' %}selected{% endif %}>Rejected</option>
                        </select>
                    </td>
                    <td>{{ record.workDuration if record.workDuration is not none else '' }}</td>
                    <td>
                        <input type="text" class="admin-remark" data-record-id="{{ record._id }}" 
                               value="{{ record.adminRemark or '' }}" placeholder="Add remark">
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <button onclick="saveChanges()" class="save-btn" style="margin-top: 20px;">Save Changes</button>
    </div>

    <script>
        let changedRecords = new Set();

        function filterRecords() {
            const userFilter = document.getElementById('userFilter').value;
            const statusFilter = document.getElementById('statusFilter').value;
            const rows = document.querySelectorAll('#pendingTable tbody tr');

            rows.forEach(row => {
                const username = row.getAttribute('data-username');
                const status = row.getAttribute('data-status');
                const userMatch = !userFilter || username === userFilter;
                const statusMatch = !statusFilter || status === statusFilter;
                row.style.display = userMatch && statusMatch ? '' : 'none';
            });
        }        

        document.querySelectorAll('.status-select').forEach(select => {
            select.addEventListener('change', function() {
                changedRecords.add(this.dataset.recordId);
                // Update the data-status attribute of the parent row
                this.closest('tr').setAttribute('data-status', this.value);
            });
        });

        function saveChanges() {
            const updates = Array.from(changedRecords).map(recordId => {
                const select = document.querySelector(`select[data-record-id="${recordId}"]`);
                const remarkInput = document.querySelector(`input.admin-remark[data-record-id="${recordId}"]`);
                
                return {
                    recordId: recordId,
                    status: select.value,
                    adminRemark: remarkInput.value
                };
            });

            if (updates.length === 0) {
                alert('No changes to save');
                return;
            }

            fetch('/update_status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ updates: updates })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert('Changes saved successfully');
                    changedRecords.clear();
                } else {
                    alert(data.message || 'Error saving changes');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error saving changes');
            });
        }
    </script>
</body>
</html>

"""

ADMIN_PROCESSED_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Processed Records - Admin Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .button-group {
            display: flex;
            gap: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .status-approved {
            color: #28a745;
            font-weight: bold;
        }
        .status-rejected {
            color: #dc3545;
            font-weight: bold;
        }
        .back-btn {
            background-color: #6c757d;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
        }
        .logout-btn {
            background-color: #dc3545;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .filter-section {
            margin-bottom: 20px;
        }
        .filter-select {
            padding: 6px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-right: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Processed Records</h1>
            <div class="button-group">
                <a href="/admin" class="back-btn">Back to Menu</a>
                <form method="POST" action="/logout" style="margin: 0;">
                    <button type="submit" class="logout-btn">Logout</button>
                </form>
            </div>
        </div>

        <div class="filter-section">
            <select id="userFilter" onchange="filterRecords()">
                <option value="">All Users</option>
                <option value="u_Nirav">Nirav</option>
                <option value="u_Vikram">Vikram</option>
                <option value="u_Mitesh">Mitesh</option>
                <option value="u_Test">Test</option>
            </select>
            <select id="statusFilter" onchange="filterRecords()">
                <option value="">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
            </select>
        </div>

        <table id="processedTable">
            <thead>
                <tr>
                    <th>Username</th>
                    <th>Action</th>
                    <th>Date & Time</th>
                    <th>User Remark</th>
                    <th>Status</th>
                    <th>Status Changed At</th>
                    <th>Work Duration (Hours)</th>
                    <th>Admin Remark</th>
                </tr>
            </thead>
            <tbody>
                {% for record in records %}
                <tr data-username="{{ record.username }}" data-status="{{ record.status }}">
                    <td>{{ record.username }}</td>
                    <td>{{ record.action }}</td>
                    <td>{{ record.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</td>
                    <td>{{ record.userRemark or '' }}</td>
                    <td class="status-{{ record.status }}">{{ record.status }}</td>
                    <td>{{ record.statusChangedAt.strftime('%Y-%m-%d %H:%M:%S') if record.statusChangedAt else '' }}</td>
                    <td>{{ record.workDuration if record.workDuration is not none else '' }}</td>
                    <td>{{ record.adminRemark or '' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    
</body>
</html>
"""    

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not logged_in_user or logged_in_user != "admin":
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route("/admin", methods=["GET"])
@admin_required
def admin_page():
    records = list(punch_collection.find().sort("timestamp", DESCENDING))
    return render_template_string(ADMIN_MENU_TEMPLATE)

@app.route("/admin/pending", methods=["GET"])
@admin_required
def admin_pending_page():
    # Only fetch pending records
    records = list(punch_collection.find({"status": "pending"}).sort("timestamp", DESCENDING))
    return render_template_string(ADMIN_PENDING_TEMPLATE, records=records)

@app.route("/admin/processed", methods=["GET"])
@admin_required
def admin_processed_page():
    # Fetch approved and rejected records
    records = list(punch_collection.find({
        "status": {"$in": ["approved", "rejected"]}
    }).sort("timestamp", DESCENDING))
    return render_template_string(ADMIN_PROCESSED_TEMPLATE, records=records)


@app.route("/update_status", methods=["POST"])
@admin_required
def update_status():
    try:
        updates = request.json.get('updates', [])
        if not updates:
            return jsonify({"status": "error", "message": "No updates provided"}), 400
            
        for update in updates:
            record_id = update['recordId']
            object_id = ObjectId(record_id)
            punch_collection.update_one(
                {"_id": object_id},
                {"$set": {
                    "status": update['status'],
                    "adminRemark": update.get('adminRemark', ''),
                    "statusChangedAt": get_time_with_offset()
                }}
            )
            
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/", methods=["GET", "POST"])
def login():
    global logged_in_user
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username in users and users[username] == password:
            logged_in_user = username
            if username == "admin":
                return redirect("/admin")
            return redirect("/main")
        return render_template_string(LOGIN_PAGE, error="Invalid credentials")
    return render_template_string(LOGIN_PAGE)

@app.route("/main")
def main_page():
    global logged_in_user
    if not logged_in_user:
        return redirect("/")
    last_punch = get_user_last_punch(logged_in_user)
    initial_status = last_punch['action'] if last_punch else None
    return render_template_string(HTML_TEMPLATE, username=logged_in_user, initial_status=initial_status)

@app.route("/logout", methods=["GET", "POST"])
def logout():
    global logged_in_user
    logged_in_user = None  # Clear the login state
    return redirect(url_for("login"))


@app.route("/get_geofence_status", methods=['POST'])
def get_geofence_status():
    global logged_in_user
    if not logged_in_user:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 403
        
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if latitude is None or longitude is None:
        return jsonify({'status': 'error', 'message': 'Missing coordinates'}), 400
        
    user_location = (float(latitude), float(longitude))
    distance = calculate_distance(user_location)
    
    status = 'Inside Geofence' if distance <= geofence_radius else 'Outside Geofence'
    return jsonify({'status': status, 'distance': distance})
    
@app.route('/last_punch_status', methods=['GET'])
def last_punch_status():
    global logged_in_user
    if not logged_in_user:
        return jsonify({'action': None})
    
    last_punch = get_user_last_punch(logged_in_user)
    if last_punch:
        return jsonify({
            'action': last_punch['action'],
            'timestamp': last_punch['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({'action': None})

@app.errorhandler(404)
def not_found_error(error):
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

@app.route('/punch', methods=['POST'])
def punch_action():
    try:
        if not logged_in_user:
            logger.error("Punch attempt without login")
            return jsonify({"status": "error", "message": "User not logged in"}), 403

        data = request.json
        logger.info(f"Received punch data: {data}")

        action = data.get('action')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        userRemark = data.get('userRemark', '')

        if not all([action, latitude is not None, longitude is not None]):
            logger.error("Missing required punch data")
            return jsonify({"status": "error", "message": "Invalid data"}), 400

        user_location = (latitude, longitude)
        distance = calculate_distance(user_location)
        logger.info(f"Distance from geofence center: {distance}")

        if distance > geofence_radius:
            logger.warning(f"User outside geofence. Distance: {distance}")
            return jsonify({"status": "error", "message": "Outside Geofence"}), 403

        current_time = get_time_with_offset()
        punch_record = {
            "username": logged_in_user,
            "action": action,
            "latitude": latitude,
            "longitude": longitude,
            "distance_from_center": distance,
            "timestamp": current_time,
            "status": "pending",
            "userRemark": userRemark,
            "statusChangedAt": None,
            "adminRemark": "",
            "workDuration": None
        }

        if action == "Punch Out":
            try:
                last_punch_in = punch_collection.find_one(
                    {
                        "username": logged_in_user,
                        "action": "Punch In"
                    },
                    sort=[("timestamp", -1)]
                )
                if last_punch_in:
                    duration = calculate_work_duration(last_punch_in['timestamp'], current_time)
                    punch_record['workDuration'] = duration
                    logger.info(f"Calculated work duration: {duration}")
            except Exception as e:
                logger.error(f"Error calculating work duration: {str(e)}")

        try:
            result = punch_collection.insert_one(punch_record)
            logger.info(f"Punch record inserted. ID: {result.inserted_id}")
            return jsonify({
                "status": "success", 
                "message": f"{action} recorded for {logged_in_user}"
            }), 200
        except Exception as e:
            logger.error(f"MongoDB insert error: {str(e)}")
            return jsonify({"status": "error", "message": "Database error"}), 500

    except Exception as e:
        logger.error(f"Punch action error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.before_request
def check_mongo_connection():
    try:
        # Ping MongoDB
        client.admin.command('ping')
    except Exception as e:
        logger.error(f"MongoDB connection error: {str(e)}")
        return jsonify({"status": "error", "message": "Database connection error"}), 500

if __name__ == '__main__':
    app.run(debug=True)

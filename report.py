import json
from werkzeug.security import generate_password_hash
from flask import Flask, render_template, jsonify, request, abort
import sqlite3
import logging
import psutil
from datetime import datetime
from app import bcolors

app = Flask(__name__, template_folder='templates')

# Liste der erlaubten IP-Adressen
ALLOWED_IPS = ['127.0.0.1', '192.168.178.81','192.168.178.194']

logging.basicConfig(filename='report.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Serverstatus abrufen
def get_flask_server_status():
    pid = psutil.Process()
    return {
        "cpu_usage": pid.cpu_percent(interval=1),
        "memory_used": pid.memory_info().rss / (1024 * 1024),  # in MB
        "disk_used": psutil.disk_usage('/').percent
    }

def get_system_status():
    return {
        "cpu_usage": psutil.cpu_percent(interval=1),
        "memory_used": psutil.virtual_memory().percent,
        "disk_used": psutil.disk_usage('/').percent
    }
    
# Variable für den initialen Wert
initial_count = 0
current_date = ""

def get_initial_count():
    """Liest den initialen Wert für den heutigen Tag aus oder speichert ihn, falls noch nicht vorhanden."""
    global initial_count, current_date
    today = datetime.today().strftime('%Y-%m-%d')
    
    try:
        conn = sqlite3.connect('datenbank.db')
        c = conn.cursor()
        
        # Überprüfen, ob der initiale Count für den aktuellen Tag in der daily_count Tabelle existiert
        c.execute("SELECT initial_count FROM daily_count WHERE date = ?", (today,))
        result = c.fetchone()
        
        if result:
            # Wenn der Wert für das heutige Datum existiert, setze den initial count
            initial_count = result[0]
            current_date = today
        else:
            # Falls der initiale Wert noch nicht gesetzt wurde, speichere ihn
            c.execute("SELECT count FROM stats WHERE page = 'index'")
            initial_count = c.fetchone()[0]
            c.execute("INSERT INTO daily_count (date, initial_count) VALUES (?, ?)", (today, initial_count))
            conn.commit()
            
        conn.close()
    except Exception as e:
        print(f"Fehler beim Abrufen oder Speichern des initialen Zählwerts: {e}")
        
def get_today_visits():
    """Berechnet die Anzahl der Zugriffe seit dem Start des Programms (Session) für den heutigen Tag."""
    global initial_count, current_date
    today = datetime.today().strftime('%Y-%m-%d')
    
    if today != current_date:
        # Falls sich das Datum geändert hat, initialisiere den Zähler für den neuen Tag
        get_initial_count()
        
    try:
        conn = sqlite3.connect('datenbank.db')
        c = conn.cursor()
        c.execute("SELECT count FROM stats WHERE page = 'index'")
        current_count = c.fetchone()[0]
        conn.close()
        
        # Berechne die Differenz zwischen aktuellem Wert und dem gespeicherten Anfangswert
        return current_count - initial_count
    except Exception as e:
        print(f"Fehler beim Berechnen der Zugriffe: {e}")
        return 0
    
# Funktion, die die Anzahl der Benutzer für jedes Alter von 9 bis 18 zählt
def count_ages():
    # Verbindung zur SQLite-Datenbank herstellen
    conn = sqlite3.connect('deine_datenbank.db')
    cursor = conn.cursor()
    
    # SQL-Abfrage, um alle Alterswerte aus der Tabelle 'benutzer' zu holen
    cursor.execute("SELECT age_user FROM benutzer")
    ages = cursor.fetchall()
    
    # Zählung der Benutzer für jedes Alter von 9 bis 18
    age_counts = {age: 0 for age in range(9, 19)}
    
    for age in ages:
        age_value = age[0]
        if 9 <= age_value <= 18:
            age_counts[age_value] += 1
            
    # Verbindung schließen
    conn.close()
    
    return age_counts

@app.before_request
def limit_remote_addr():
    client_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
   # Zeigt die IP-Adresse und den User-Agent in der Konsole an
    print(f'{bcolors.HEADER}Zugriffsversuch von IP: {client_ip}, User-Agent: {user_agent}{bcolors.ENDC}')
    
    # Überprüfen, ob die Client-IP in der Liste der erlaubten IPs ist
    if client_ip not in ALLOWED_IPS:
        # Zugriff verweigern und die error.html Seite laden
        return render_template('error.html', error_message="Zugriff verweigert"), 403        

@app.route('/', methods=['GET', 'POST'])
def report():
    # Aktuelles Datum im Format YYYY-MM-DD
    heute = datetime.today().strftime('%Y-%m-%d')
    try:
        # Datenbankverbindung herstellen
        conn = sqlite3.connect('datenbank.db')
        c = conn.cursor()

        # Datenbankabfragen
        c.execute("SELECT COUNT(*) FROM benutzer")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM benutzer WHERE ip_address != '0'")
        total_valid_users = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM benutzer WHERE category = 'Gast'")
        total_guests = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM stats WHERE page = 'index'")
        total_visits = c.fetchone()[0]
        
        # Holen der Anzahl der Zugriffe für heute
        visits_today = get_today_visits()
        
        c.execute("SELECT COUNT(*) FROM benutzer WHERE category ='Gast' AND strftime('%Y-%m-%d', anmeldedatum) = ? AND bezahlt = 1", (heute,))
        guests_today = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM benutzer WHERE bezahlt = 1")
        total_paid = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM benutzer WHERE category = 'Team'")
        team_member_count = c.fetchone()[0]
        
        # Einnahmen und Gutscheine
        revenue = total_paid * 2
        vouchers = total_paid * 2

        # Ressourcenstatus abrufen
        flask_server_status = get_flask_server_status()
        system_status = get_system_status()

        # Fehlerprotokolle abrufen
        try:
            with open('report.log', 'r') as log_file:
                error_logs = log_file.readlines()[-10:]  # Letzte 10 Zeilen
        except FileNotFoundError:
            error_logs = ["Keine Fehlerprotokolle gefunden."]

        conn.close()

        # Bericht rendern
        return render_template(
            'report.html',
            total_users=total_users,
            total_guests=total_guests,
            total_paid=total_paid,
            revenue=revenue,
            vouchers=vouchers,
            flask_server_status=flask_server_status,
            system_status=system_status,
            error_logs=error_logs,
        )
    except Exception as e:
        logging.error(f"Fehler beim Abrufen der Report-Daten: {str(e)}")
        return render_template('error.html', error_message="Ein Fehler ist aufgetreten."), 500
    finally:
        # Verbindung sicher schließen
        if conn:
            conn.close()
            
@app.route('/table', methods=['GET'])
def table():
    try:
        # Verbindung zur Datenbank herstellen
        conn = sqlite3.connect('datenbank.db')
        c = conn.cursor()
        
        # Letzte 50 Einträge abrufen
        c.execute("SELECT * FROM benutzer ORDER BY id DESC")
        entries = c.fetchall()
        
        # Spaltennamen abrufen
        column_names = [description[0] for description in c.description]
        
        conn.close()
        
        # Daten als JSON zurückgeben
        return {"columns": column_names, "entries": entries}
    except Exception as e:
        logging.error(f"Fehler beim Abrufen der Tabelle: {str(e)}")
        return {"error": "Ein Fehler ist aufgetreten."}, 500
    
@app.route('/team', methods=['GET'])
def team():
    try:
        conn = sqlite3.connect('datenbank.db')
        c = conn.cursor()
        
        # Daten der Team-Mitglieder abrufen
        c.execute("SELECT vorname, nachname, alter FROM benutzer WHERE category = 'Team'")
        team_members = c.fetchall()
        
        conn.close()
        
        # Als JSON zurückgeben
        return {"team_members": team_members}
    except Exception as e:
        logging.error(f"Fehler beim Abrufen der Team-Daten: {str(e)}")
        return {"error": "Ein Fehler ist aufgetreten."}, 500
    
# API-Endpunkt, um die Altersverteilung zurückzugeben
@app.route('/age_statistics')
def get_age_statistics():
    # Die Altersverteilung zählen
    age_stats = count_ages()
    
    # Rückgabe der Altersverteilung als JSON
    return jsonify(age_stats)
    

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8292, debug=True)
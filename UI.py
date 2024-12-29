import tkinter as tk
from tkinter import Tk,ttk,  Label, PhotoImage, messagebox
import sqlite3
from datetime import datetime
from PIL import Image, ImageTk  # Pillow importieren
import subprocess


conn = sqlite3.connect('datenbank.db')
cursor = conn.cursor()  # Cursor erstellen

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'  
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

start_ssh_path = 'HostDeploySP.ssh'
stop_ssh_path = 'global STOP.sh'
action_stack = []  # Stapel für vergangene Aktionen
undo_stack = []
redo_stack = []    # Stapel für rückgängig gemachte Aktionen

# Globale Variable für den Verbindungsstatus
db_connected = False  # Anfangs keine Verbindung

# Funktion für die Verbindung zur Datenbank
def bounce_icon(icon_name, steps=5, interval=50):
    #Lässt das Icon hüpfen, außer es ist das Standard-Icon.
    if icon_name == "Standard":
        return
    else:
        def bounce_step(step):
            if step <= steps:
                # Bewegung nach oben und unten
                offset = -step if step % 2 == 0 else step
                canvas.move(icon_label, 0, offset)
                root.after(interval, bounce_step, step + 1)
            else:
                # Zurücksetzen der Position
                canvas.move(icon_label, 0, -steps)
                
        bounce_step(1)
    
def update_button_states():
    undo_button["state"] = "normal" if action_stack else "disabled"
    redo_button["state"] = "normal" if redo_stack else "disabled"

def undo_last_action():
    if not action_stack:
        log_message("Keine Aktion zum Rückgängig machen.", highlight=True)
        return
    
    last_action = action_stack.pop()
    redo_stack.append(last_action)  # Für Redo speichern
    
    action_type = last_action["type"]
    data = last_action["data"]
    
    if action_type == "update_payment":
        # Bezahlstatus in `benutzer` zurücksetzen
        cursor.execute("UPDATE benutzer SET bezahlt = ?, scanned = 0 WHERE identifier = ?", 
                       (data["old_value"], data["identifier"]))
        conn.commit()
        
        # Eintrag aus `PayState_scanned` entfernen, falls rückgängig gemacht
        if data["old_value"] == 0:
            cursor.execute("DELETE FROM PayState_scanned WHERE identifier = ?", (data["identifier"],))
        else:
            # Auf alten Wert zurücksetzen
            cursor.execute("""
                UPDATE PayState_scanned 
                SET bezahlt = ?, category = ? 
                WHERE identifier = ?
            """, (data["old_value"], data["old_category"], data["identifier"]))
        conn.commit()
        
        log_message(f"Bezahlstatus für '{data['identifier']}' und Eintrag in `PayState_scanned` rückgängig gemacht.", highlight=True)
        
    elif action_type == "update_category":
        # Kategorie in `benutzer` zurücksetzen
        cursor.execute("UPDATE benutzer SET category = ? WHERE identifier = ?", 
                       (data["old_category"], data["identifier"]))
        conn.commit()
        log_message(f"Kategorie für '{data['identifier']}' auf '{data['old_category']}' zurückgesetzt.", highlight=True)
        
    elif action_type == "add_entry":
        # Eintrag aus `benutzer` entfernen
        cursor.execute("DELETE FROM benutzer WHERE identifier = ?", (data["identifier"],))
        conn.commit()
        log_message(f"Eintrag für '{data['identifier']}' entfernt.", highlight=True)
        
    # UI-Änderungen rückgängig machen
    ui_updates = last_action.get("ui_updates")
    if ui_updates and "table_row_id" in ui_updates:
        table.delete(ui_updates["table_row_id"])
        
    update_button_states()
    
def connect_to_db():
    global conn, cursor, db_connected
    if db_connected:
        # Verbindung trennen
        try:
            conn.close()
            db_connected = False
            log_message("Datenbankverbindung geschlossen.", highlight=True)
            status_label.config(text="Datenbank: Nicht verbunden", fg="red")
            connect_button.config(text="Datenbank verbinden")
        except sqlite3.Error as e:
            log_message(f"Fehler beim Schließen der Datenbankverbindung: {e}")
    else:
        # Verbindung herstellen
        try:
            conn = sqlite3.connect("datenbank.db")
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            db_connected = True
            log_message("Datenbankverbindung erfolgreich hergestellt.", highlight=True)
            status_label.config(text="Datenbank: Verbunden", fg="green")
            connect_button.config(text="Verbindung abbrechen")
        except sqlite3.Error as e:
            log_message(f"Fehler bei der Datenbankverbindung: {e}", highlight=True)
            status_label.config(text="Datenbank: Nicht verbunden", fg="red")
        
def log_message(message, highlight=False, sql=None, parameters=None, error=None):
    #Loggt eine Nachricht im Verlauf. Optional: SQL-Fehlerdetails.
    log_area.config(state="normal")  # Bearbeitbar machen
    
    # Highlight hervorheben
    if highlight:
        log_area.insert(tk.END, message + "\n", "highlight")
    else:
        log_area.insert(tk.END, message + "\n")
        
    # SQL und Fehlerdetails hinzufügen, falls vorhanden
    if sql and parameters:
        log_area.insert(tk.END, f"SQL-Abfrage: {sql}\nParameter: {parameters}\n", "warning")
    if error:
        log_area.insert(tk.END, f"Fehler: {error}\n", "warning")
        
    log_area.config(state="disabled")  # Wieder schreibgeschützt machen
    log_area.see(tk.END)  # Automatisch scrollen
    
# Funktion, um nur die Daten für den aktuellen Identifier anzuzeigen und die Historie zu bewahren
def show_scanned_data(identifier):
    cursor.execute("SELECT vorname, nachname, age_user, jahrgang, category, bezahlt FROM PayState_scanned WHERE identifier = ?", (identifier,))
    result = cursor.fetchone()
    if result:
        vorname, nachname, age_user, jahrgang, category, bezahlt = result
        Bezahlt = "Bezahlt" if bezahlt == 1 else "Nicht Bezahlt"
        table.insert("", "0", values=(vorname, nachname, age_user, jahrgang, category, Bezahlt))
        log_message(f"Daten für Identifier '{identifier}' angezeigt.", highlight=True)
    else:
        log_message(f"Keine Daten für Identifier '{identifier}' gefunden.", highlight=True)
    

# Funktion, um ein Bild zu skalieren und in PhotoImage zu konvertieren
def load_and_scale_icon(path, size=(100, 100)):
    img = Image.open(path)  # Bild laden
    img = img.resize(size, Image.LANCZOS)  # Bild skalieren
    return ImageTk.PhotoImage(img)  # In ein Tkinter-kompatibles Bild konvertieren

def start_action():
    try:
        # Führe das Start-Skript (HostDeploy.ssh) aus
        subprocess.run(["bash", "/Users/can/Desktop/Ticketverkauf/HostDeploySP.sh"], check=True)
        messagebox.showinfo("Info", "Start-Skript ausgeführt!")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Fehler", f"Fehler beim Ausführen des Start-Skripts: {e}")
        
def stop_action():
    try:
        # Führe das Stopp-Skript (STOP.ssh) aus
        subprocess.run(["bash", "global_STOP.sh"], check=True)
        messagebox.showinfo("Info", "Stopp-Skript ausgeführt!")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Fehler", f"Fehler beim Ausführen des Stopp-Skripts: {e}")

def toggle_mode():
    #Zwischen 'Verkauf' und 'Einlass' wechseln.
    current_mode = mode_var.get()
    new_mode = "Einlass" if current_mode == "Verkauf" else "Verkauf"
    mode_var.set(new_mode)
    toggle_button.config(text=f"Modus: {new_mode}")
    
    # Checkbox deaktivieren/aktivieren
    if new_mode == "Einlass":
        checkbutton.config(state="disabled")  # Deaktivieren
        next_scan_as_team.set(False)  # Sicherheitshalber zurücksetzen
        log_message("Einlass-Modus: Checkbox deaktiviert.")
    else:
        checkbutton.config(state="normal")  # Aktivieren
        log_message("Verkaufs-Modus: Checkbox aktiviert.")

def show_info():
    messagebox.showinfo("Info", "Dies ist ein Ticketverkaufssystem!")

# Hauptfenster
root = tk.Tk()
root.title("Ticketverkauf Schulparty 24.01.25")
root.geometry("800x600")
root.iconbitmap("/Users/can/Desktop/Ticketverkauf/static/favicon.ico")

# Variable für das Kontrollkästchen
next_scan_as_team = tk.BooleanVar(value=False)

# Canvas oben rechts für das Symbol
canvas = tk.Canvas(root, width=100, height=100)
canvas.place(x=740, y=10)

# Funktion zum Ändern des Symbols
def update_icon(icon_name):
    #Aktualisiert das angezeigte Icon im Label.
    if icon_name in icons:
        icon_label.config(image=icons[icon_name])
        bounce_icon(icon_name)
    else:
        icon_label.config(image=icons["Standard"])  # Fallback auf Standard
        
scanned_identifiers = set()

def process_input(event):
    identifier = event.widget.get()
    show_scanned_data(identifier)
    # Eingabefeld leeren
    entry.delete(0, tk.END)
    if identifier not in scanned_identifiers:
        scanned_identifiers.add(identifier)
        show_scanned_data(identifier)
    else:
        print(f"Ticket '{identifier}' wurde bereits gescannt.")
    # Überprüfen des Modus
    current_mode = mode_var.get()
    if current_mode == "Verkauf":

        # Im Verkaufsmodus: Bezahlstatus auf TRUE (1) setzen
        try:
            # Aktuelle Zeit holen
            last_scantime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Überprüfen, ob der Identifier existiert
            cursor.execute("SELECT vorname, nachname, age_user, jahrgang, category, bezahlt FROM benutzer WHERE identifier = ?", (identifier,))
            result = cursor.fetchone()
            
            if result:
                vorname, nachname, age_user, jahrgang, category, bezahlt = result
                update_icon("Standard")  # Standard-Icon anzeigen
                
                # Kategorie ändern, falls Kontrollkästchen aktiv ist
                if next_scan_as_team.get():
                    # Nächster Scan als Team
                    category = "Team"
                    next_scan_as_team.set(False)  # Checkbox zurücksetzen
                    checkbutton.deselect()
                    log_message(f"Kategorie für '{identifier}' auf 'Team' gesetzt.")
                
                action_stack.append({
                    "type": "update_category",
                    "data": {
                        "identifier": identifier,
                        "old_category": "Gast",
                        "new_category": "Team"
                    }
                })
                redo_stack.clear()
    
                    
                # Überprüfen, ob der Benutzer bereits bezahlt hat
                if bezahlt == 1:
                    log_message(f"Benutzer '{identifier}' hat bereits bezahlt.", highlight=True)
                    update_icon("Warning")  # Warn-Icon anzeigen
                    
                elif bezahlt == 0:
                    # Speichern der Aktion im action_stack
                    action_stack.append({
                        "type": "update_payment",
                        "data": {
                            "identifier": identifier,
                            "old_value": bezahlt,
                            "new_value": 1
                        }
                    })
                    redo_stack.clear()  # Redo-Stapel leeren
                    
                    # Bezahlstatus in der `benutzer`-Tabelle auf TRUE setzen
                    cursor.execute("""
                        UPDATE benutzer
                        SET bezahlt = 1, last_scantime = ?, scanned = COALESCE(scanned, 0) + 1, category = ?
                        WHERE identifier = ?
                    """, (last_scantime, category, identifier))
                    conn.commit()
                    
                    log_message(f"Bezahlstatus für Benutzer '{identifier}' auf bezahlt gesetzt.")
                    
                    # Daten in die `PayState_scanned`-Tabelle eintragen
                    cursor.execute("""
                        INSERT INTO PayState_scanned (identifier, vorname, nachname, age_user, jahrgang, bezahlt, category)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(identifier) DO UPDATE SET
                        bezahlt = excluded.bezahlt,
                        category = excluded.category
                    """, (identifier, vorname, nachname, age_user, jahrgang, 1, category))
                    conn.commit()
                    
                    log_message(f"Eintrag für '{identifier}' in PayState_scanned aktualisiert.")
                    
                    # Daten für den aktuellen Identifier anzeigen
                    show_scanned_data(identifier)
                    
                else:
                    log_message(f"Unerwarteter Bezahlstatus für '{identifier}'.")
                    update_icon("Warning")
            else:
                log_message(f"Keine Benutzerdaten für Identifier '{identifier}' gefunden.")
                update_icon("Warning")
                
        except sqlite3.Error as e:
            log_message(f"Datenbankfehler beim Verarbeiten des Identifiers '{identifier}': {e}")
            
    
    else:  # Wenn im Modus 'Einlass'
        try:
            #Daten aus Tabelle abrufen
            cursor.execute("SELECT vorname, nachname, age_user, jahrgang, category, bezahlt, scanned FROM benutzer WHERE identifier = ?", (identifier,))
            result = cursor.fetchone()
            
            if result:
                vorname, nachname, age_user, jahrgang, category, bezahlt, scanned = result  # Nimmt alle sieben Werte
                    
                if category == "Team":
                    Bezahlt = "Bezahlt"
                    status = "Team"
                    update_icon("Team")
                    
                elif category == "Gast" and bezahlt == 0:
                    Bezahlt ="Nicht Bezahlt"
                    status = "Gast"
                    update_icon("No")
                elif bezahlt == 1 and scanned <= 1:
                    Bezahlt = "Bezahlt"
                    status = "Gast"
                    update_icon("Yes")
                    # Wert für 'scanned' um 1 erhöhen
                    cursor.execute("UPDATE benutzer SET scanned = scanned + 1 WHERE identifier = ?", (identifier,))
                    conn.commit()
                    # Aktion: Scanzähler erhöhen
                    action_stack.append({
                        "type": "update_scan",
                        "data": {
                            "identifier": identifier,
                            "old_scanned": scanned,
                            "new_scanned": scanned + 1
                        }
                    })
                    redo_stack.clear()  # Redo-Stapel leeren

                elif bezahlt == 1 and scanned == 2:
                    Bezahlt = "Bereits Gescannt"
                    status = "Gast"
                    update_icon("Warning")
                elif category == "Team" and scanned > 1:
                    Bezahlt = "Team - Bezahlt"
                    Status = "Team"
                    update_icon("YesNo")
                    
                # Daten in die Tabelle eintragen
                table.insert("", "0", values=(vorname, nachname, age_user, jahrgang, status))
                show_scanned_data(identifier)
                # Verlauf aktualisieren
                log_area.config(state="normal")
                log_area.insert("end", f"{identifier} - {category} (Scanned: {scanned})\n")
                log_area.config(state="disabled")
                log_message(f"{identifier}' abgerufen. Scanned: {scanned}",highlight=True)
            else:
                log_message(f"Keine Daten für Identifier '{identifier}' gefunden.")
                
        except sqlite3.Error as e:
            log_message(f"Datenbankfehler: {e}")
            
    
#    update_button_states()  # Button-Zustände aktualisieren
    
# Menüleiste
menu_bar = tk.Menu(root)
file_menu = tk.Menu(menu_bar, tearoff=0)
# Statussymbol für die Verbindung
status_label = tk.Label(root, text="Datenbank: Nicht verbunden", fg="red", font=("Arial", 10))
status_label.pack(pady=5)
file_menu.add_command(label="Datenbank verbinden", command=connect_to_db)
file_menu.add_separator()
file_menu.add_command(label="Beenden", command=root.quit)
menu_bar.add_cascade(label="Datei", menu=file_menu)

options_menu = tk.Menu(menu_bar, tearoff=0)
options_menu.add_command(label="Info", command=show_info)
menu_bar.add_cascade(label="Optionen", menu=options_menu)

root.config(menu=menu_bar)

# Eingabebereich
entry_label = tk.Label(root, text="Barcode Scannen:")
entry_label.pack(pady=10)

entry = tk.Entry(root, font=("Arial", 14))
entry.pack(pady=10)
# Das Eingabefeld wird auf die Funktion process_input gebunden
entry.bind("<Return>", process_input)


# Buttons für Aktionen (muss vor dem Checkbutton definiert sein)
button_frame = tk.Frame(root)
button_frame.pack(pady=10)

# Kontrollkästchen hinzufügen
checkbutton = tk.Checkbutton(
    button_frame, 
    text="Nächster Scan als Team", 
    variable=next_scan_as_team, 
    onvalue=True, 
    offvalue=False
)
checkbutton.pack(side="left", padx=5)
# Buttons für Aktionen
button_frame = tk.Frame(root)
button_frame.pack(pady=10)

connect_button = tk.Button(button_frame, text="Datenbank verbinden", command=connect_to_db)
connect_button.pack(side="left", padx=5)


# Icons initialisieren und skalieren
icons = {
    "Yes": load_and_scale_icon("static/images/icons/Yes.png"),
    "No": load_and_scale_icon("static/images/icons/NO.png"),
    "Standard": load_and_scale_icon("static/images/icons/standard.png"),
    "Warning": load_and_scale_icon("static/images/icons/Warning.png"),
    "Team": load_and_scale_icon("static/images/icons/Team.png"),
    "YesNo": load_and_scale_icon("static/images/icons/yesbut.png"),
}

# Label für das Symbol oben rechts hinzufügen
icon_label = Label(root, image=icons["Standard"])  # Startet mit Standard-Icon
icon_label.place(relx=0.95, rely=0.05, anchor="ne")  # Oben rechts positionieren


mode_var = tk.StringVar(value="Verkauf")
toggle_button = tk.Button(button_frame, text="Modus: Verkauf", command=toggle_mode)
toggle_button.pack(side="left", padx=5)

info_button = tk.Button(button_frame, text="Info", command=show_info)
info_button.pack(side="left", padx=5)

## Bilder für undo/redo Buttons laden
#undo_icon = Image.open("static/images/icons/undoRedo.png").convert("RGBA")# Tranzparenz sicherstellen
#undoInac_icon = Image.open("static/images/icons/undoRedo_inactive.png").convert("RGBA")
#
## Redo-Bilder durch Spiegelung erzeugen
#redo_icon = undo_icon.transpose(Image.FLIP_LEFT_RIGHT)
#redoInac_icon = undoInac_icon.transpose(Image.FLIP_LEFT_RIGHT)
#
## In Tkinter-kompatible Bilder konvertieren
#undo_icon_tk = ImageTk.PhotoImage(undo_icon)
#undoInac_icon_tk = ImageTk.PhotoImage(undoInac_icon)
#redo_icon_tk = ImageTk.PhotoImage(redo_icon)
#redoInac_icon_tk = ImageTk.PhotoImage(redoInac_icon)
#
#undo_button = tk.Button(
#   button_frame, 
##    image=undo_icon_tk, 
#   text="Undo",
#   command=undo_last_action, 
#   borderwidth=0, 
#   highlightthickness=10, 
#   bg="#2b2b2b",  # Hintergrund passend zur Anwendung
#   activebackground="#2b2b2b",  # Aktiver Hintergrund ebenfalls angepasst
#   relief=tk.FLAT  # Entfernt jegliche 3D-Effekte
#)
#undo_button.pack(side="left", padx=5)
#
#redo_button = tk.Button(
#   button_frame, 
##   image=redo_icon_tk, 
#   text="Redo",
#   command=redo_last_action, 
#   borderwidth=0, 
#   highlightthickness=0, 
#   bg="#2b2b2b", 
#   activebackground="#2b2b2b",
#   relief=tk.FLAT
#)
#redo_button.pack(side="left", padx=5)

# Verlauf
log_label = tk.Label(root, text="Verlauf:")
log_label.pack(pady=5)

log_area = tk.Text(root, height=8, state="normal", wrap="word", bg="#2b2b2b", fg="white", font=("Courier", 10))
log_area.pack(padx=10, pady=5, fill="both")
log_area.tag_configure("warning", foreground="yellow", font=("bold"))
log_area.tag_configure("error", foreground="red", font=("bold"))
log_area.tag_configure("success", foreground="green")
log_area.tag_configure("highlight", foreground="yellow", font=("Courier", 10, "bold"))

log_area.tag_configure("good", foreground="green", font=("Courier", 10, "bold"))


# Tabelle
table_label = tk.Label(root, text="Daten:")
table_label.pack(pady=5)

columns = ( "Vorname", "Nachname", "Alter", "Klasse", "Status", "Bezahlt")
table = ttk.Treeview(root, columns=columns, show="headings")

for col in columns:
    table.heading(col, text=col)
    table.column(col, width=120)

table.pack(pady=10, fill="both", expand=True)

# Start der Anwendung
root.mainloop()
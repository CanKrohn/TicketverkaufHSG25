#!/bin/bash
# Port definieren
PORT=8292  # Passe den Port an, den du überprüfen möchtest
# Prozesse beenden, die den Port verwenden
echo "Suche Prozesse auf Port $PORT..."
lsof -ti tcp:$PORT | xargs -r kill -9
echo "Alle Prozesse auf Port $PORT wurden beendet."

IP=$(ifconfig en0 | grep "inet " | awk '{print $2}')
GREEN="\033[0;32m"
RESET="\033[0m"
echo -e "${GREEN}Server wird gestartet. Erreichbar unter: http://$IP:$PORT${RESET}"

# Verzeichnis des aktuellen Skripts ermitteln
SCRIPT_DIR=$(dirname "$(realpath "$0")")
echo "Wechsle in das Verzeichnis: $SCRIPT_DIR"
cd "$SCRIPT_DIR"



# Virtuelle Umgebung aktivieren
if [ -f venv/bin/activate ]; then
    echo "Aktiviere die virtuelle Umgebung..."
    source venv/bin/activate
#    pip install -r /Users/can/Desktop/Ticketverkauf/Requirements.txt
else
    echo "Virtuelle Umgebung nicht gefunden!"
    exit 1
fi
echo "Starte Python-Anwendung..."
python3 report.py



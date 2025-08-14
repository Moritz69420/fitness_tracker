from flask import Flask, render_template, redirect, url_for, request
import plotly.io as pio
import plotly.graph_objects as go
import sqlite3
import pandas as pd
import os

app = Flask(__name__)

# Deine importierten Funktionen
from main_strava import plot_interaktiver_tss_sticks, rolling_averag_n, reboot

def get_activities_table_data(limit=50):
    """
    Holt die letzten Aktivitäten aus der Datenbank für die Tabelle
    
    Args:
        limit (int): Anzahl der Aktivitäten, die geholt werden sollen
    
    Returns:
        list: Liste von Dictionaries mit Aktivitätsdaten
    """
    conn = sqlite3.connect("strava_data.db")
    
    query = """
    SELECT 
        activity_name,
        start_date,
        distanz,
        elevation_gain,
        moving_time,
        sport,
        tss
    FROM aktivitaeten 
    WHERE activity_name IS NOT NULL
    ORDER BY start_date DESC 
    LIMIT ?
    """
    
    df = pd.read_sql_query(query, conn, params=[limit])
    conn.close()
    
    # Daten formatieren
    activities = []
    for _, row in df.iterrows():
        # Zeit von Sekunden in HH:MM:SS umwandeln
        moving_time_seconds = row['moving_time'] if row['moving_time'] else 0
        hours = int(moving_time_seconds // 3600)
        minutes = int((moving_time_seconds % 3600) // 60)
        formatted_time = f"{hours:02d}:{minutes:02d}" if hours > 0 else f"{minutes:02d}min"
        
        # Distanz von Metern in Kilometer umwandeln
        distance_km = round(row['distanz'] / 1000, 1) if row['distanz'] else 0
        
        # Datum formatieren
        try:
            date_obj = pd.to_datetime(row['start_date'])
            formatted_date = date_obj.strftime("%d.%m")
        except:
            formatted_date = row['start_date']
        
        # Höhenmeter formatieren
        elevation = int(row['elevation_gain']) if row['elevation_gain'] else 0
        
        # TSS formatieren
        tss = int(row['tss']) if row['tss'] else 0
        
        # Aktivitätsname kürzen falls zu lang
        activity_name = row['activity_name']
        if len(activity_name) > 25:
            activity_name = activity_name[:22] + "..."
        
        activities.append({
            'name': activity_name,
            'date': formatted_date,
            'distance': f"{distance_km}km",
            'elevation': f"{elevation}m",
            'time': formatted_time,
            'sport': row['sport'][:4] if row['sport'] else "",  # Sport abkürzen
            'tss': tss
        })
    
    return activities

@app.route("/")
def index():
    # Rolling averages holen
    rolling_avg_7, tss_per_day_7 = rolling_averag_n(7)
    rolling_avg_42, tss_per_day_42 = rolling_averag_n(42)
    
    # Plotly Figure generieren
    fig = plot_interaktiver_tss_sticks(tss_per_day_7, rolling_avg_7, rolling_avg_42, wochenfenster=6, return_fig=True)
    
    # Figure als HTML-String (div) exportieren
    plot_html = pio.to_html(fig, full_html=False)
    
    # Aktivitäten für Tabelle holen
    activities = get_activities_table_data(30)  # Letzte 30 Aktivitäten (anpassbar)
    
    # Render HTML Template mit Plotly Div und Aktivitäten
    return render_template("index.html", plot_div=plot_html, activities=activities)

@app.route("/reboot", methods=["POST"])
def reboot_route():
    reboot()  # Deine Updatefunktion ausführen
    return redirect(url_for("index"))  # Zurück zur Startseite (mit neuem Plot)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # holt PORT von Render, sonst 5000 lokal
    app.run(host="0.0.0.0", port=port)
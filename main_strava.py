import math
import urllib3
import sqlite3
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from tabulate import tabulate
from datetime import datetime
import subprocess
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_strava_data_200():
    auth_url = "https://www.strava.com/oauth/token"
    activites_url = "https://www.strava.com/api/v3/athlete/activities"

    payload = {
        'client_id': "170429",
        'client_secret': 'e231dc2bb14aa44848628e8d052b716cc4f55f3e',
        'refresh_token': '933201b48fdfae35afe1fecd179a6dec3948f3e3',
        'grant_type': "refresh_token",
        'f': 'json'
    }

    print("Requesting Token...\n")
    res = requests.post(auth_url, data=payload, verify=False)
    access_token = res.json()['access_token']
    # print("Access Token = {}\n".format(access_token))

    header = {'Authorization': 'Bearer ' + access_token}
    param = {'per_page': 200, 'page': 1}
    my_dataset = requests.get(activites_url, headers=header, params=param).json()

    return my_dataset


def get_strava_all_data():
    """
    exports all the strava acitivities on my strava account
    """
    auth_url = "https://www.strava.com/oauth/token"
    activites_url = "https://www.strava.com/api/v3/athlete/activities"

    payload = {
        'client_id': "170429",
        'client_secret': 'e231dc2bb14aa44848628e8d052b716cc4f55f3e',
        'refresh_token': '933201b48fdfae35afe1fecd179a6dec3948f3e3',
        'grant_type': "refresh_token",
        'f': 'json'
    }

    print("Requesting Token...\n")
    res = requests.post(auth_url, data=payload, verify=False)
    access_token = res.json()['access_token']

    #print("Access Token = {}\n".format(access_token))
    header = {'Authorization': 'Bearer ' + access_token}

    # The first loop, request_page_number will be set to one, so it requests the first page. Increment this number after
    # each request, so the next time we request the second page, then third, and so on...
    request_page_num = 1
    all_activities = []

    while True:
        param = {'per_page': 200, 'page': request_page_num}
        # initial request, where we request the first page of activities
        my_dataset = requests.get(activites_url, headers=header, params=param).json()

        # check the response to make sure it is not empty. If it is empty, that means there is no more data left. So if you have
        # 1000 activities, on the 6th request, where we request page 6, there would be no more data left, so we will break out of the loop
        if len(my_dataset) == 0:
            print("breaking out of while loop because the response is zero, which means there must be no more activities")
            break

        # if the all_activities list is already populated, that means we want to add additional data to it via extend.
        if all_activities:
            print("all_activities is populated")
            all_activities.extend(my_dataset)

        # if the all_activities is empty, this is the first time adding data so we just set it equal to my_dataset
        else:
            print("all_activities is NOT populated")
            all_activities = my_dataset

        request_page_num += 1

    return all_activities


def data_into_database(input_data: list):
    """
    uses input list and formats them into "strava_data.db"
    """
    conn = sqlite3.connect("strava_data.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS aktivitaeten (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_name TEXT,
        strava_id INTEGER,
        start_date TEXT,
        moving_time INTEGER,
        sport TEXT,
        subsport TEXT,
        polyline TEXT,
        distanz REAL,
        elevation_gain REAL,
        avg_speed REAL,
        max_speed REAL,
        avg_cadence REAL,
        avg_hr REAL,
        max_hr REAL,
        avg_watts REAL,
        kilojoules REAL
    )
    """)

    for activity in input_data[::-1]:
        strava_id = activity["id"]
        cursor.execute("SELECT 1 FROM aktivitaeten WHERE strava_id = ?", (strava_id,))
        exists = cursor.fetchone()
        if not exists:
            cursor.execute("""
            INSERT INTO aktivitaeten 
            (activity_name, strava_id, start_date, moving_time, sport, subsport, polyline, distanz, elevation_gain, avg_speed, max_speed, avg_cadence, avg_hr, max_hr, avg_watts, kilojoules) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                activity.get("name"),
                activity.get("id"),
                activity.get("start_date_local"),
                activity.get("moving_time"),
                activity.get("type"),
                activity.get("sport_type"),
                activity.get("map", {}).get("summary_polyline"),
                activity.get("distance"),
                activity.get("total_elevation_gain"),
                activity.get("average_speed"),
                activity.get("max_speed"),
                activity.get("average_cadence"),
                activity.get("average_heartrate"),
                activity.get("max_heartrate"),
                activity.get("average_watts"),
                activity.get("kilojoules")
            ))
    conn.commit()

    conn.close()


def calc_tss(id: int):
    """
    Takes the id of an activity und calculates the according tss and enters it into a seperate tss column.
    """
    FTP_bike = 300
    FTP_run = 280
    conn = sqlite3.connect("strava_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT moving_time, avg_watts, sport FROM aktivitaeten WHERE id = ?", (id,))
    values = cursor.fetchall()
    duration, watts, sport = values[0]
    if sport == "Ride":
        tss = round(duration/3600 * (watts/FTP_bike)**2 * 100)
    elif sport == "Run":
        tss = round((duration/3600 * (watts/FTP_run)**2 * 100)*1.3)
    else:
        print("unbekannte Sportart")
    cursor.execute("UPDATE aktivitaeten SET tss = ? WHERE id = ?", (tss, id))
    # Print ergebnis
    cursor.execute("SELECT activity_name FROM aktivitaeten WHERE id = ?", (id,))
    name = cursor.fetchall()[0][0]
    print(f"Added {tss} tss to activity '{name}' : Nr.:{id}.")

    conn.commit()
    conn.close()



def add_tss_to_all_activities(db_path="strava_data.db", ftp_bike=300, ftp_run=280, debug=True):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Versuche, die TSS-Spalte hinzuzufügen (nur einmal nötig)
    try:
        cursor.execute("ALTER TABLE aktivitaeten ADD COLUMN tss REAL")
        if debug: print("Spalte 'tss' wurde hinzugefügt.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            if debug: print("Spalte 'tss' existiert bereits.")
        else:
            raise

    # Hole alle Aktivitäten ohne TSS
    cursor.execute("SELECT id, moving_time, avg_watts, sport, activity_name FROM aktivitaeten WHERE tss IS NULL")
    activities = cursor.fetchall()
    if debug: print(f"{len(activities)} Aktivitäten ohne TSS gefunden.")


## TSS ausrechenen
    for id, duration, watts, sport, name in activities:
        
        try:
            if watts is None or duration is None:
                tss = 0
                if debug: print(f"⚠️ {name} (ID {id}): Fehlende Daten (watts={watts}, duration={duration}) → TSS = 0")
        
            elif sport == "Ride":
                tss = round(duration / 3600 * (watts / ftp_bike)**2 * 100)
            elif sport == "Run":
                tss = round(duration / 3600 * (watts / ftp_run)**2 * 100 * 1.3)
            else:
                # Unbekannte Sportart → explizit als NaN markieren, damit sie beim nächsten Mal ignoriert wird
                tss = 0
                if debug: print(f"❌ {name} (ID {id}): Unbekannte Sportart '{sport}' → TSS = NaN")

            cursor.execute("UPDATE aktivitaeten SET tss = ? WHERE id = ?", (tss, id))
            if not math.isnan(tss) and debug:
                print(f"✅ {name} (ID {id}): TSS = {tss}")

        except Exception as e:
            print(f"⚠️ Fehler bei Aktivität {id}: {e}")

    conn.commit()
    conn.close()



def add_tss_to_activities():
    conn = sqlite3.connect("strava_data.db")
    cursor = conn.cursor()

    conn = sqlite3.connect("strava_data.db")
    cursor = conn.cursor()

    # Neue Spalte "tss" vom Typ REAL hinzufügen (wenn sie noch nicht existiert)
    try:
        cursor.execute("ALTER TABLE aktivitaeten ADD COLUMN tss REAL")
        print("Spalte 'tss' wurde hinzugefügt.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Spalte 'tss' existiert bereits.")
        else:
            raise

    # Hole alle IDs von Aktivitäten ohne TSS-Wert
    cursor.execute("SELECT id FROM aktivitaeten WHERE tss IS NULL")
    activity_ids = [row[0] for row in cursor.fetchall()]

    print(f"{len(activity_ids)} Aktivitäten ohne TSS gefunden.")

    for activity_id in activity_ids:
        try:
            tss = calc_tss(activity_id)
            if tss is not None:
                cursor.execute("UPDATE aktivitaeten SET tss = ? WHERE id = ?", (tss, activity_id))
                print(f"TSS für Aktivität {activity_id} gespeichert: {tss:.2f}")
        except Exception as e:
            print(f"Fehler bei Aktivität {activity_id}: {e}")

    conn.commit()
    conn.close()


def rolling_averag_n(n:int):
    """
    Errechnet den rolling average über die letzen n Tage und gibt zwei pandas Series aus mit
    den täglichen Tss und eine mit den rolling averages über n Tage
    """
    # Verbindung zur Datenbank
    conn = sqlite3.connect("strava_data.db")

    # SQL-Abfrage: Datum und TSS-Wert
    query = "SELECT start_date, tss FROM aktivitaeten WHERE tss IS NOT NULL"
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Datum konvertieren (ist im Format: 2020-01-04T11:16:05Z)
    df["start_date"] = pd.to_datetime(df["start_date"])

    # Sicherstellen, dass wir mit UTC-Zeit rechnen
    df["start_date"] = df["start_date"].dt.tz_convert("UTC") if df["start_date"].dt.tz is not None else df["start_date"].dt.tz_localize("UTC")

    # Index setzen
    df = df.set_index("start_date")

    # Tägliche TSS-Werte berechnen (leere Tage → 0)
    tss_per_day = df["tss"].resample("D").sum().fillna(0)

    # Rolling Average über 7 Tage inkl. freier Tage
    rolling = tss_per_day.rolling(window=n, min_periods=1).mean().round()
    # print(df["tss"].idxmax())
    # Ausgabe
    print("TSS pro Tag:")
    # print(tss_per_day.tail(n+5))
    # print(f"\nRolling Average ({n} Tage):")
    # print(rolling.tail(n+5))
    return rolling, tss_per_day


def plot_interaktiver_tss_sticks(tss_per_day: pd.Series, rolling_7: pd.Series, rolling_42: pd.Series, wochenfenster: int = 6, return_fig=False):
    df_plot = pd.DataFrame({
        "datum": tss_per_day.index,
        "tss_per_day": tss_per_day.values,
        "rolling 7": rolling_7.values,
        "rolling 42": rolling_42.values
    })

    ###### Alternative Colorway ######
    # tss_color = '#374151'
    # seven_line_color = '#34D399'
    # fourtytwo_line_color = '#A78BFA'
    # seven_shade_color = 'rgba(52, 211, 153, 0.25)'
    # fourtytwo_shade_color = 'rgba(167, 139, 250, 0.15)'
    # background_colour = '#0F172A'

    tss_color = '#A3A3A3'
    seven_line_color = '#EC4899'
    fourtytwo_line_color = '#84CC16'
    seven_shade_color = 'rgba(236, 72, 153, 0.25)'
    fourtytwo_shade_color = 'rgba(132, 204, 22, 0.15)'
    background_colour = '#FAFAFA'

    # tss_color = "#520923"  # chocolate-cosmos
    # seven_line_color = '#dc2f02'  # sinopia - feuriges Rot
    # fourtytwo_line_color = '#f48c06'  # princeton-orange
    # seven_shade_color = 'rgba(220, 47, 2, 0.22)'
    # fourtytwo_shade_color = 'rgba(244, 140, 6, 0.15)'
    # background_colour = '#03071e'  # rich-black - dunkler Hintergrund

    fig = go.Figure()

    # TSS als vertikale Striche (Bar)
    fig.add_trace(go.Bar(
        x=df_plot["datum"],
        y=df_plot["tss_per_day"],
        name="TSS pro Tag",
        marker_color = tss_color,
        opacity=0.5,
    ))

    # 7-Tage Rolling Average (Linie mit Füllung)
    fig.add_trace(go.Scatter(
        x=df_plot["datum"],
        y=df_plot["rolling 7"],
        mode='lines+markers',
        name="Rolling 7",
        line=dict(color= seven_line_color, width=3),
        fill='tozeroy',
        fillcolor= seven_shade_color  # orange, transparent
    ))

    # 42-Tage Rolling Average (Linie mit Füllung)
    fig.add_trace(go.Scatter(
        x=df_plot["datum"],
        y=df_plot["rolling 42"],
        mode='lines+markers',
        name="Rolling 42",
        line=dict(color=fourtytwo_line_color, width=3),
        fill='tozeroy',
        fillcolor= fourtytwo_shade_color   # grün, noch transparenter
    ))

    # X-Achse begrenzen auf Wochenfenster
    max_datum = df_plot["datum"].max()
    min_datum = max_datum - pd.Timedelta(weeks=wochenfenster)
    fig.update_xaxes(range=[min_datum, max_datum])

    fig.update_layout(
        title="Täglicher TSS und Rolling Averages",
        xaxis_title="Datum",
        yaxis_title="TSS",
        barmode='overlay',  # Bars überlappen Linien nicht
        template='plotly_white',
        plot_bgcolor= background_colour,
        paper_bgcolor= background_colour,
        font=dict(color='black'),
        dragmode="pan",
        yaxis=dict(
            range=[0, 500],         # Nur Y-Werte von 0 bis 600 sichtbar
            fixedrange=True        # True = kein Scroll/Zoom auf Y-Achse möglich
        )
    )

    fig.update_layout(
    legend=dict(
        x=0,       # 0 = ganz links, 1 = ganz rechts
        y=1.15,    # >1 ist über der Plotfläche (weiter oben)
        bgcolor='rgba(0,0,0,0)',  # transparent
        orientation='h'  # horizontal (optional)
    )
)

    fig.update_layout(
        xaxis=dict(
            color='#3f3f3f'  # Achsentext, Ticks, Linie
        ),
        yaxis=dict(
            color='#3f3f3f'
        )
    )

    fig.update_layout(
        xaxis=dict(
            showgrid=False,
            gridcolor='#3f3f3f'  # horizontale Rasterlinien
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#3f3f3f'  # vertikale Rasterlinien
        )
    )
    fig.update_layout(
        xaxis=dict(
            tickmode="linear",      # lineare Ticks
            dtick="D1",             # 1 Tag Abstand
            tickformat="%d.%m",     # Format: Tag.Monat (z. B. 07.08)
            tickangle=-45,          # Schräge Labels für mehr Platz
            tickfont=dict(size=9)  # Kleinere Schrift
        )
    )
    if return_fig:
        return fig
    else:
        fig.show()



def plot_graph():
    rolling_avg_7, tss_per_day_7 = rolling_averag_n(7)
    rolling_avg_42, tss_per_day_42 = rolling_averag_n(42)
    # rolling_avg_42, tss_per_day_42 = rolling_averag_42()
    # rolling_avg_7, tss_per_day_7 = rolling_averag_7()
    plot_interaktiver_tss_sticks(tss_per_day_7, rolling_avg_7, rolling_avg_42)


def export_db_table_to_txt(db_path, table_name, exclude_columns=None, output_prefix="db_export"):
    """
    Exportiert den Inhalt einer SQLite-Tabelle als Texttabelle in eine .txt-Datei.

    Args:
        db_path (str): Pfad zur .db Datei.
        table_name (str): Name der Tabelle, die exportiert werden soll.
        output_prefix (str): Prefix für die Output-Datei.
        exclude_columns (list[str], optional): Liste von Spaltennamen, die nicht exportiert werden sollen.
    
    Returns:
        str: Pfad zur erstellten .txt-Datei.
    """
    exclude_columns = exclude_columns or []

    # Verbindung herstellen
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Spaltennamen ermitteln
    cursor.execute(f"PRAGMA table_info({table_name})")
    all_columns = [col[1] for col in cursor.fetchall()]
    
    # Exportierte Spalten bestimmen
    selected_columns = [col for col in all_columns if col not in exclude_columns]
    column_string = ", ".join(selected_columns)

    # Daten abrufen
    cursor.execute(f"SELECT {column_string} FROM {table_name}")
    daten = cursor.fetchall()

    # Verbindung schließen
    conn.close()

    # Tabelle formatieren
    tabelle = tabulate(daten, headers=selected_columns, tablefmt="grid")

    # Dateiname generieren
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dateiname = f"{output_prefix}_{table_name}_{timestamp}.txt"

    # In Datei schreiben
    with open(dateiname, "w", encoding="utf-8") as f:
        f.write(tabelle)

    print(f"✅ Export abgeschlossen: {dateiname}")
    return dateiname


def reboot():
    """Aktualisiert die Datenbank von Strava, berechnet TSS und committet ins Git-Repo."""
    # 1️⃣ Neue Aktivitäten laden & TSS berechnen
    data_into_database(get_strava_data_200())
    add_tss_to_all_activities()
    # export_db_table_to_txt("strava_data.db", "aktivitaeten", "polyline")

    # 2️⃣ Git-Commit + Push
    try:
        subprocess.run(["git", "add", "strava_data.db"], check=True)
        commit_msg = f"Update Strava-Datenbank {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ Änderungen ins GitHub-Repo gepusht!")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Git-Fehler: {e}")


if __name__ == "__main__":
    reboot()
    # export_db_table_to_txt("strava_data.db", "aktivitaeten", "polyline")
    # plot_graph()
    # add_tss_to_all_activities()
    print("this is main")
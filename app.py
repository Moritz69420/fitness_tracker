from flask import Flask, render_template, redirect, url_for, request
import plotly.io as pio
import plotly.graph_objects as go
import os

app = Flask(__name__)

# Deine importierten Funktionen
from main_strava import plot_interaktiver_tss_sticks, rolling_averag_n, reboot

@app.route("/")
def index():
    # Rolling averages holen
    rolling_avg_7, tss_per_day_7 = rolling_averag_n(7)
    rolling_avg_42, tss_per_day_42 = rolling_averag_n(42)

    # Plotly Figure generieren
    fig = plot_interaktiver_tss_sticks(tss_per_day_7, rolling_avg_7, rolling_avg_42, wochenfenster=6, return_fig=True)

    # Figure als HTML-String (div) exportieren
    plot_html = pio.to_html(fig, full_html=False)

    # Render HTML Template mit Plotly Div
    return render_template("index.html", plot_div=plot_html)

@app.route("/reboot", methods=["POST"])
def reboot_route():
    reboot()  # Deine Updatefunktion ausführen
    return redirect(url_for("index"))  # Zurück zur Startseite (mit neuem Plot)




if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # holt PORT von Render, sonst 5000 lokal
    app.run(host="0.0.0.0", port=port)

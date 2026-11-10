AgriLink 2.0 - Smart Farm-to-Processor Platform (Agriculture & Food Processing)

RUN (Windows PowerShell, inside this folder - the one that contains app.py):
  python -m venv venv
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  venv\Scripts\activate
  pip install -r requirements.txt
  python app.py
Open http://127.0.0.1:5000   (internet needed for Chart.js / Leaflet map CDNs)

Delete agrilink.db before running if you used the older version.

DEMO FLOW: Dashboard -> Marketplace -> "Find processors" on an urgent lot -> Accept deal
-> Dashboard numbers update. Then show Map and List Produce (auto-fills shelf life + market price).

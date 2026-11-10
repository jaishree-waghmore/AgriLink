from flask import Flask, jsonify, request, render_template
import sqlite3, math
from datetime import date, timedelta

app = Flask(__name__)
DB = "agrilink.db"

# (lat, lng) of Karnataka districts - used for the map and distance-based matching
DISTRICTS = {
    "Bengaluru": (12.97, 77.59), "Kolar": (13.14, 78.13), "Mysuru": (12.30, 76.64),
    "Hassan": (13.00, 76.10), "Mandya": (12.52, 76.90), "Tumakuru": (13.34, 77.10),
    "Shivamogga": (13.93, 75.57), "Dharwad": (15.46, 75.01), "Belagavi": (15.85, 74.50),
    "Kalaburagi": (17.33, 76.83), "Ballari": (15.14, 76.92), "Udupi": (13.34, 74.75),
}
# Demo reference data (indicative, replace with live mandi API in production)
REF_PRICE = {"tomato": 15, "mango": 45, "potato": 20, "banana": 28, "milk": 44,
             "chilli": 60, "wheat": 26, "onion": 22, "chicken": 160}
SHELF = {"tomato": 7, "mango": 8, "potato": 60, "banana": 6, "milk": 2,
         "chilli": 10, "wheat": 180, "onion": 45, "chicken": 3}
PROCESSING = {
    "tomato": [("Tomato puree", 2.0), ("Ketchup", 2.5), ("Sun-dried tomato", 3.0)],
    "milk": [("Paneer", 1.8), ("Ghee", 2.5), ("Curd / Yogurt", 1.4)],
    "mango": [("Mango pulp", 2.0), ("Aam papad", 2.8), ("Pickle", 2.2)],
    "potato": [("Chips", 3.0), ("Frozen fries", 2.5), ("Starch", 1.8)],
    "banana": [("Banana chips", 3.0), ("Banana flour", 2.2)],
    "chilli": [("Chilli powder", 2.0), ("Chilli sauce", 2.5)],
    "wheat": [("Atta (flour)", 1.3), ("Semolina (rava)", 1.5)],
    "onion": [("Dehydrated onion", 2.6), ("Onion paste", 2.0)],
    "chicken": [("Frozen / marinated chicken", 1.6), ("Ready-to-cook packs", 2.0)],
}


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return round(6371 * 2 * math.asin(math.sqrt(h)))


def init_db():
    c = get_db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS produce (
        id INTEGER PRIMARY KEY AUTOINCREMENT, farmer TEXT NOT NULL, category TEXT NOT NULL,
        crop TEXT NOT NULL, quantity_kg INTEGER NOT NULL, price_per_kg REAL NOT NULL,
        district TEXT NOT NULL, harvest_date TEXT NOT NULL, shelf_life_days INTEGER NOT NULL,
        contact TEXT, status TEXT DEFAULT 'available');
    CREATE TABLE IF NOT EXISTS demands (
        id INTEGER PRIMARY KEY AUTOINCREMENT, processor TEXT NOT NULL, crop TEXT NOT NULL,
        quantity_kg INTEGER NOT NULL, offer_price REAL NOT NULL, district TEXT NOT NULL,
        product TEXT, contact TEXT);
    CREATE TABLE IF NOT EXISTS deals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, produce_id INTEGER, demand_id INTEGER,
        offer_price REAL, created TEXT);
    """)
    if c.execute("SELECT COUNT(*) FROM produce").fetchone()[0] == 0:
        t = date.today()
        P = [("Suresh Gowda", "Crop", "Tomato", 800, 12, "Kolar", 4, 7, "9876500001"),
             ("Anita Patil", "Crop", "Mango", 500, 40, "Dharwad", 2, 8, "9876500002"),
             ("Mahesh Reddy", "Crop", "Potato", 2000, 18, "Hassan", 10, 60, "9876500003"),
             ("Kavita Naik", "Crop", "Banana", 600, 25, "Mysuru", 3, 6, "9876500004"),
             ("Raju Singh", "Dairy", "Milk", 300, 45, "Belagavi", 0, 2, "9876500005"),
             ("Lakshmi Bai", "Crop", "Chilli", 250, 55, "Ballari", 5, 10, "9876500006"),
             ("Manjunath K", "Livestock", "Chicken", 400, 150, "Shivamogga", 1, 3, "9876500007"),
             ("Imran Pasha", "Crop", "Onion", 1500, 20, "Mandya", 12, 45, "9876500008"),
             ("Sunitha R", "Crop", "Tomato", 600, 14, "Bengaluru", 5, 7, "9876500009")]
        c.executemany("INSERT INTO produce (farmer,category,crop,quantity_kg,price_per_kg,district,harvest_date,shelf_life_days,contact) VALUES (?,?,?,?,?,?,?,?,?)",
                      [(a, b, cr, q, p, d, (t - timedelta(days=ago)).isoformat(), s, ct) for a, b, cr, q, p, d, ago, s, ct in P])
        D = [("FreshPulp Foods", "Tomato", 1500, 16, "Bengaluru", "Tomato puree", "9000000001"),
             ("Karnataka Dairy Co-op", "Milk", 500, 50, "Belagavi", "Paneer & ghee", "9000000002"),
             ("Mango Magic Pvt Ltd", "Mango", 800, 48, "Dharwad", "Mango pulp", "9000000003"),
             ("CrispyChips Ltd", "Potato", 3000, 22, "Mysuru", "Potato chips", "9000000004"),
             ("SpiceRoots", "Chilli", 400, 62, "Ballari", "Chilli powder", "9000000005"),
             ("GoldenBanana Foods", "Banana", 700, 30, "Mysuru", "Banana chips", "9000000006"),
             ("HealthyBite Meats", "Chicken", 600, 165, "Tumakuru", "Frozen chicken", "9000000007"),
             ("OnionPlus Dehydrators", "Onion", 2000, 24, "Tumakuru", "Dehydrated onion", "9000000008")]
        c.executemany("INSERT INTO demands (processor,crop,quantity_kg,offer_price,district,product,contact) VALUES (?,?,?,?,?,?,?)", D)
    c.commit()
    c.close()


def lot(r):
    d = dict(r)
    expiry = date.fromisoformat(d["harvest_date"]) + timedelta(days=d["shelf_life_days"])
    d["days_left"] = (expiry - date.today()).days
    d["shelf_pct"] = round(100 * d["days_left"] / max(d["shelf_life_days"], 1))
    ref = REF_PRICE.get(d["crop"].lower())
    d["ref_price"] = ref
    d["verdict"] = None if not ref else ("Below market" if d["price_per_kg"] < ref * 0.9 else "Above market" if d["price_per_kg"] > ref * 1.1 else "Fair price")
    ll = DISTRICTS.get(d["district"])
    d["lat"], d["lng"] = (ll if ll else (None, None))
    return d


def all_lots(conn, where="", params=()):
    return [lot(r) for r in conn.execute("SELECT * FROM produce " + where, params).fetchall()]


def need(d, keys):
    return any(not str(d.get(k, "")).strip() for k in keys)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/meta")
def meta():
    return jsonify({"districts": DISTRICTS, "shelf": SHELF, "ref_price": REF_PRICE})


@app.route("/api/produce", methods=["GET"])
def list_produce():
    q, dist, cat = (request.args.get(k, "").strip() for k in ("q", "district", "category"))
    urgent, sort = request.args.get("urgent") == "1", request.args.get("sort", "urgency")
    sql, p = "WHERE 1=1", []
    if q: sql += " AND (crop LIKE ? OR farmer LIKE ?)"; p += [f"%{q}%"] * 2
    if dist: sql += " AND district=?"; p.append(dist)
    if cat: sql += " AND category=?"; p.append(cat)
    conn = get_db()
    rows = all_lots(conn, sql, p)
    conn.close()
    if urgent: rows = [r for r in rows if r["days_left"] <= 3 and r["status"] == "available"]
    key = {"price": lambda r: r["price_per_kg"], "quantity": lambda r: -r["quantity_kg"]}.get(sort, lambda r: (r["status"] != "available", r["days_left"]))
    return jsonify(sorted(rows, key=key))


@app.route("/api/produce", methods=["POST"])
def add_produce():
    d = request.get_json() or {}
    if need(d, ["farmer", "crop", "quantity_kg", "price_per_kg", "district", "harvest_date", "shelf_life_days"]):
        return jsonify({"error": "Please fill all required fields"}), 400
    try:
        conn = get_db()
        conn.execute("INSERT INTO produce (farmer,category,crop,quantity_kg,price_per_kg,district,harvest_date,shelf_life_days,contact) VALUES (?,?,?,?,?,?,?,?,?)",
                     (d["farmer"], d.get("category", "Crop"), d["crop"].strip().title(), int(d["quantity_kg"]), float(d["price_per_kg"]),
                      d["district"], d["harvest_date"], int(d["shelf_life_days"]), d.get("contact", "")))
        conn.commit(); conn.close()
    except ValueError:
        return jsonify({"error": "Quantity, price and shelf life must be numbers"}), 400
    return jsonify({"message": "ok"}), 201


@app.route("/api/demands", methods=["GET", "POST"])
def demands():
    conn = get_db()
    if request.method == "POST":
        d = request.get_json() or {}
        if need(d, ["processor", "crop", "quantity_kg", "offer_price", "district"]):
            return jsonify({"error": "Please fill all required fields"}), 400
        try:
            conn.execute("INSERT INTO demands (processor,crop,quantity_kg,offer_price,district,product,contact) VALUES (?,?,?,?,?,?,?)",
                         (d["processor"], d["crop"].strip().title(), int(d["quantity_kg"]), float(d["offer_price"]),
                          d["district"], d.get("product", ""), d.get("contact", "")))
            conn.commit()
        except ValueError:
            return jsonify({"error": "Quantity and price must be numbers"}), 400
        return jsonify({"message": "ok"}), 201
    rows = [dict(r) for r in conn.execute("SELECT * FROM demands ORDER BY id DESC").fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/match/<int:pid>")
def match(pid):
    conn = get_db()
    r = conn.execute("SELECT * FROM produce WHERE id=?", (pid,)).fetchone()
    if not r:
        return jsonify({"error": "Not found"}), 404
    p = lot(r)
    out = []
    for d in conn.execute("SELECT * FROM demands").fetchall():
        if d["crop"].lower() != p["crop"].lower():
            continue
        a, b = DISTRICTS.get(p["district"]), DISTRICTS.get(d["district"])
        dist = km(a, b) if a and b else 250
        price_pts = 10 if d["offer_price"] >= p["price_per_kg"] else round(10 * d["offer_price"] / p["price_per_kg"])
        score = 50 + (20 if p["days_left"] <= 3 else 10) + round(20 * (1 - min(dist, 400) / 400)) + price_pts
        qty = min(p["quantity_kg"], d["quantity_kg"])
        out.append({**dict(d), "distance_km": dist, "score": min(score, 100),
                    "coverage": min(100, round(100 * d["quantity_kg"] / p["quantity_kg"])),
                    "farmer_gain": round((d["offer_price"] - p["price_per_kg"]) * qty)})
    conn.close()
    return jsonify({"lot": p, "matches": sorted(out, key=lambda m: -m["score"])[:5]})


@app.route("/api/deal", methods=["POST"])
def deal():
    d = request.get_json() or {}
    conn = get_db()
    p = conn.execute("SELECT * FROM produce WHERE id=? AND status='available'", (d.get("produce_id"),)).fetchone()
    dm = conn.execute("SELECT * FROM demands WHERE id=?", (d.get("demand_id"),)).fetchone()
    if not p or not dm:
        return jsonify({"error": "Lot already matched or not found"}), 400
    conn.execute("UPDATE produce SET status='matched' WHERE id=?", (p["id"],))
    conn.execute("INSERT INTO deals (produce_id,demand_id,offer_price,created) VALUES (?,?,?,?)",
                 (p["id"], dm["id"], dm["offer_price"], date.today().isoformat()))
    conn.commit(); conn.close()
    return jsonify({"message": "Deal confirmed"})


@app.route("/api/suggest/<int:pid>")
def suggest(pid):
    conn = get_db()
    r = conn.execute("SELECT * FROM produce WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not r:
        return jsonify({"error": "Not found"}), 404
    raw = r["quantity_kg"] * r["price_per_kg"]
    ideas = PROCESSING.get(r["crop"].lower(), [("Drying / dehydration", 1.5), ("Cold storage", 1.2)])
    return jsonify({"crop": r["crop"], "raw_value": round(raw),
                    "ideas": [{"product": n, "value": round(raw * m), "gain": round(raw * (m - 1))} for n, m in ideas]})


@app.route("/api/stats")
def stats():
    conn = get_db()
    lots = all_lots(conn)
    avail = [l for l in lots if l["status"] == "available"]
    deals = conn.execute("""SELECT d.offer_price, d.created, p.quantity_kg q, p.price_per_kg pp, p.crop, p.farmer, m.processor
                            FROM deals d JOIN produce p ON p.id=d.produce_id JOIN demands m ON m.id=d.demand_id
                            ORDER BY d.id DESC""").fetchall()
    conn.close()
    by_crop, value = {}, {}
    for l in avail:
        k = l["crop"]
        by_crop[k] = by_crop.get(k, 0) + l["quantity_kg"]
        mult = max([m for _, m in PROCESSING.get(k.lower(), [("", 1.5)])])
        raw = l["quantity_kg"] * l["price_per_kg"]
        v = value.setdefault(k, [0, 0])
        v[0] += round(raw); v[1] += round(raw * mult)
    urgent = [l for l in avail if 0 <= l["days_left"] <= 3]
    return jsonify({
        "listed_kg": sum(l["quantity_kg"] for l in avail), "farmers": len({l["farmer"] for l in lots}),
        "urgent_lots": len(urgent), "at_risk_kg": sum(l["quantity_kg"] for l in urgent),
        "rescued_kg": sum(d["q"] for d in deals),
        "extra_income": round(sum((d["offer_price"] - d["pp"]) * d["q"] for d in deals)),
        "deals": len(deals), "by_crop": by_crop, "value": value,
        "feed": [{"text": f"{d['processor']} bought {d['crop']} from {d['farmer']}", "kg": d["q"]} for d in deals[:6]],
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True)

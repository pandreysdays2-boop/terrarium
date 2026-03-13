import os, json, time
from flask import Flask, render_template, jsonify, request
try:
    import requests as _requests
except ImportError:
    _requests = None

app = Flask(__name__)

# ════════════════════════════════════════════════════════
#  CONFIG — set these in Render's Environment tab
# ════════════════════════════════════════════════════════

UPLOAD_SECRET   = os.environ.get("UPLOAD_SECRET", "change-this-before-deploying")
JSONBIN_BIN_ID  = os.environ.get("JSONBIN_BIN_ID", "")   # your bin ID from jsonbin.io
JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY", "")  # your API key from jsonbin.io

BASE        = os.path.dirname(os.path.abspath(__file__))
LOCAL_GRAPH = os.path.join(BASE, "graph_log.json")


# ════════════════════════════════════════════════════════
#  SAMPLE / DEFAULT DATA
# ════════════════════════════════════════════════════════

SAMPLE_GRAPH = {
    "points": [
        {"ts": time.time()-3600*8, "step": 0,    "train": 4.82, "val": 4.90, "best_val": 4.90, "stage": "Stage 1 · Pretrain"},
        {"ts": time.time()-3600*7, "step": 1000, "train": 4.21, "val": 4.35, "best_val": 4.35, "stage": "Stage 1 · Pretrain"},
        {"ts": time.time()-3600*6, "step": 2000, "train": 3.98, "val": 4.10, "best_val": 4.10, "stage": "Stage 1 · Pretrain"},
        {"ts": time.time()-3600*5, "step": 3000, "train": 3.80, "val": 3.92, "best_val": 3.92, "stage": "Stage 1 · Pretrain"},
        {"ts": time.time()-3600*4, "step": 4000, "train": 3.71, "val": 3.84, "best_val": 3.84, "stage": "Stage 1 · Pretrain"},
        {"ts": time.time()-3600*3, "step": 5000, "train": 3.62, "val": 3.76, "best_val": 3.76, "stage": "Stage 2 · Mid"},
        {"ts": time.time()-3600*2, "step": 6000, "train": 3.54, "val": 3.65, "best_val": 3.65, "stage": "Stage 2 · Mid"},
        {"ts": time.time()-3600*1, "step": 7000, "train": 3.48, "val": 3.56, "best_val": 3.56, "stage": "Stage 2 · Mid"},
        {"ts": time.time()-1800,   "step": 8000, "train": 3.42, "val": 3.49, "best_val": 3.49, "stage": "Stage 2 · Mid"},
        {"ts": time.time()-600,    "step": 9000, "train": 3.38, "val": 3.47, "best_val": 3.47, "stage": "Stage 2 · Mid"},
    ],
    "best_val": 3.47,
    "stage": "Stage 2 · Mid",
    "updated": time.time() - 600,
    "_is_sample": True
}

DEFAULT_RUNS = [
    {
        "id": 18, "name": "Run 18", "stage": "2-Stage Pipeline",
        "best_val": 3.3355, "start": "2026-03-12", "status": "complete",
        "notes": "New best. 2-stage pipeline. Best val at step 58600.",
        "sample_text": "The story of the day before yesterday's party of consternation is not a dream, said the citizen, though in his lower mind he spoke as an inquest of events. — It's no matter, sir. — I fear it's not the best in the world, Martin Cunningham said."
    },
    {
        "id": 17, "name": "Run 17", "stage": "2-Stage Pipeline",
        "best_val": 3.4735, "start": "2026-03-10", "status": "complete",
        "notes": "Previous best. 2-stage pipeline confirmed working.",
        "sample_text": ""
    },
]


# ════════════════════════════════════════════════════════
#  JSONBIN — permanent run storage
# ════════════════════════════════════════════════════════

JSONBIN_HEADERS = lambda: {
    "Content-Type": "application/json",
    "X-Master-Key": JSONBIN_API_KEY,
    "X-Bin-Versioning": "false",
}

def jsonbin_read():
    """Read runs from JSONBin. Returns list or None on failure."""
    if not JSONBIN_BIN_ID or not JSONBIN_API_KEY or not _requests:
        return None
    try:
        r = _requests.get(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest",
            headers=JSONBIN_HEADERS(), timeout=5
        )
        if r.status_code == 200:
            return r.json().get("record", {}).get("runs")
    except Exception:
        pass
    return None

def jsonbin_write(runs):
    """Write runs to JSONBin. Returns True on success."""
    if not JSONBIN_BIN_ID or not JSONBIN_API_KEY or not _requests:
        return False
    try:
        r = _requests.put(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}",
            headers=JSONBIN_HEADERS(),
            json={"runs": runs},
            timeout=5
        )
        return r.status_code == 200
    except Exception:
        return False


# ════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════

def read_json(path):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return None

def write_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def auth_ok():
    return request.headers.get("X-Secret") == UPLOAD_SECRET

def load_runs():
    """Load runs from JSONBin, fall back to defaults."""
    runs = jsonbin_read()
    return runs if runs else DEFAULT_RUNS


# ════════════════════════════════════════════════════════
#  PAGES
# ════════════════════════════════════════════════════════

@app.route("/")
def terrarium():
    return render_template("terrarium.html")

@app.route("/runs")
def runs():
    return render_template("runs.html", runs=load_runs())

@app.route("/info")
def info():
    return render_template("info.html")


# ════════════════════════════════════════════════════════
#  API — READ
# ════════════════════════════════════════════════════════

# All-time best val floor — update this after each run
ALL_TIME_BEST = 3.3105  # Run 19, step 74800

@app.route("/api/graph_log")
def api_graph_log():
    data = read_json(LOCAL_GRAPH)
    if data:
        # Clamp best_val to all-time floor so it never shows worse than history
        if data.get("best_val") is not None:
            data["best_val"] = min(data["best_val"], ALL_TIME_BEST)
    return jsonify(data if data else SAMPLE_GRAPH)

@app.route("/api/status")
def api_status():
    data = read_json(LOCAL_GRAPH)
    if data:
        pts  = data.get("points", [])
        last = pts[-1] if pts else {}
        age  = time.time() - data.get("updated", 0)
        best = data.get("best_val")
        if best is not None:
            best = min(best, ALL_TIME_BEST)
        return jsonify({
            "training":    age < 120,
            "stage":       data.get("stage", ""),
            "best_val":    best,
            "step":        last.get("step"),
            "val":         last.get("val"),
            "train":       last.get("train"),
            "updated_ago": int(age),
        })
    return jsonify({
        "training": False, "stage": "Stage 2 · Mid",
        "best_val": ALL_TIME_BEST, "step": 60000,
        "val": 3.3105, "train": 2.86,
        "updated_ago": 999, "_is_sample": True,
    })


# ════════════════════════════════════════════════════════
#  API — PUSH  (protected by UPLOAD_SECRET)
# ════════════════════════════════════════════════════════

@app.route("/api/push_graph", methods=["POST"])
def push_graph():
    if not auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No JSON"}), 400
    try:
        write_json_atomic(LOCAL_GRAPH, data)
        return jsonify({"ok": True, "points": len(data.get("points", []))})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug")
def api_debug():
    """Check JSONBin config and connectivity."""
    has_bin = bool(JSONBIN_BIN_ID)
    has_key = bool(JSONBIN_API_KEY)
    runs = jsonbin_read()
    return jsonify({
        "jsonbin_bin_id_set": has_bin,
        "jsonbin_api_key_set": has_key,
        "runs_loaded": runs is not None,
        "run_count": len(runs) if runs else 0,
    })


@app.route("/api/push_runs", methods=["POST"])
def push_runs():
    """Receives runs from admin.py and saves to JSONBin permanently."""
    if not auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(silent=True)
    if not body or "runs" not in body:
        return jsonify({"error": "No runs list"}), 400
    runs = body["runs"]
    ok = jsonbin_write(runs)
    if ok:
        return jsonify({"ok": True, "runs": len(runs), "storage": "jsonbin"})
    # JSONBin not configured — fall back to local file
    try:
        write_json_atomic(os.path.join(BASE, "runs_data.json"), runs)
        return jsonify({"ok": True, "runs": len(runs), "storage": "local"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True, port=5001)

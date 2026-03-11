import os, json, time
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# ════════════════════════════════════════════════════════
#  CONFIG
#  On Railway: set these in the Variables tab
#  Locally:    they fall back to the defaults below
# ════════════════════════════════════════════════════════

UPLOAD_SECRET = os.environ.get("UPLOAD_SECRET", "change-this-before-deploying")

# Files stored next to app.py on the Railway server
BASE        = os.path.dirname(os.path.abspath(__file__))
LOCAL_GRAPH = os.path.join(BASE, "graph_log.json")
LOCAL_RUNS  = os.path.join(BASE, "runs_data.json")


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
        "id": 17, "name": "Run 17", "stage": "2-Stage Pipeline",
        "best_val": 3.4735, "start": "2026-03-10", "status": "complete",
        "notes": "All-time best. 2-stage pipeline confirmed working.",
        "sample_text": ""
    },
]


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


# ════════════════════════════════════════════════════════
#  PAGES
# ════════════════════════════════════════════════════════

@app.route("/")
def terrarium():
    return render_template("terrarium.html")

@app.route("/runs")
def runs():
    run_list = read_json(LOCAL_RUNS) or DEFAULT_RUNS
    return render_template("runs.html", runs=run_list)

@app.route("/info")
def info():
    return render_template("info.html")


# ════════════════════════════════════════════════════════
#  API — READ
# ════════════════════════════════════════════════════════

@app.route("/api/graph_log")
def api_graph_log():
    data = read_json(LOCAL_GRAPH)
    return jsonify(data if data else SAMPLE_GRAPH)

@app.route("/api/status")
def api_status():
    data = read_json(LOCAL_GRAPH)
    if data:
        pts  = data.get("points", [])
        last = pts[-1] if pts else {}
        age  = time.time() - data.get("updated", 0)
        return jsonify({
            "training":    age < 120,
            "stage":       data.get("stage", ""),
            "best_val":    data.get("best_val"),
            "step":        last.get("step"),
            "val":         last.get("val"),
            "train":       last.get("train"),
            "updated_ago": int(age),
        })
    return jsonify({
        "training": False, "stage": "Stage 2 · Mid",
        "best_val": 3.4735, "step": 9000,
        "val": 3.47, "train": 3.38,
        "updated_ago": 999, "_is_sample": True,
    })


# ════════════════════════════════════════════════════════
#  API — PUSH  (protected by UPLOAD_SECRET)
# ════════════════════════════════════════════════════════

@app.route("/api/push_graph", methods=["POST"])
def push_graph():
    """Receives graph_log.json from admin.py or push_graph.py."""
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


@app.route("/api/push_runs", methods=["POST"])
def push_runs():
    """Receives the published runs list from admin.py."""
    if not auth_ok():
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(silent=True)
    if not body or "runs" not in body:
        return jsonify({"error": "No runs list"}), 400
    try:
        write_json_atomic(LOCAL_RUNS, body["runs"])
        return jsonify({"ok": True, "runs": len(body["runs"])})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True, port=5001)

from flask import Flask, render_template, request, send_file, after_this_request, jsonify
import os
import time
import threading
import pandas as pd
from engine.cache import RateCache
from engine.pricing import process_manifest

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "import_data")
RESULT_FOLDER = os.path.join(os.path.dirname(__file__), "export_data")
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "data.xlsx")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# Pre-warm RateCache in memory on startup (instant subsequent calculations)
print(">>> Warming RevenueApp v3 Rate Cache...")
t0 = time.time()
rate_cache = RateCache(DATA_FILE)
print(f">>> Rate Cache pre-warmed in {time.time()-t0:.2f}s!")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return "No file uploaded", 400

    file = request.files["file"]
    if file.filename == "":
        return "No file selected", 400

    # Save uploaded file
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(input_path)

    # Read uploaded file
    t_start = time.time()
    if file.filename.lower().endswith(".csv"):
        manifest_df = pd.read_csv(input_path)
    else:
        manifest_df = pd.read_excel(input_path)

    # Run v3 high-speed in-memory pricing engine
    result_df = process_manifest(manifest_df, rate_cache)
    calc_ms = int((time.time() - t_start) * 1000)

    # Save output CSV
    result_filename = f"result_{int(time.time())}.csv"
    output_path = os.path.join(RESULT_FOLDER, result_filename)
    result_df.to_csv(output_path, index=False)
    print(f"[REVENUE ENGINE] Processed {len(manifest_df)} rows in {calc_ms}ms -> {result_filename}")

    # File cleanup
    @after_this_request
    def remove_files(response):
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
        except Exception as e:
            app.logger.error(f"Error deleting input file: {e}")

        def cleanup_output():
            time.sleep(10)
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except Exception as e:
                app.logger.error(f"Error deleting output file: {e}")

        threading.Thread(target=cleanup_output).start()
        response.headers["X-Processing-Time-Ms"] = str(calc_ms)
        return response

    return send_file(output_path, as_attachment=True, download_name=result_filename)

@app.route("/available_clients")
def available_clients():
    try:
        clients = sorted(list(set(client for client, _ in rate_cache.cbm_rules.keys() if client)))
        return jsonify({"clients": clients})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/deploy-pull", methods=["POST"])
def deploy_pull():
    import subprocess
    token = request.headers.get("X-Deploy-Token")
    expected_token = os.environ.get("DEPLOY_TOKEN", "revenue-v3-secret-sync")
    if not token or token != expected_token:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        cmd = ["git", "pull", "origin", "main"]
        result = subprocess.run(cmd, cwd=app_dir, capture_output=True, text=True, check=True)
        return jsonify({"status": "success", "output": result.stdout}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

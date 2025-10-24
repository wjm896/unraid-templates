from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
import os
import shutil
import difflib
import json
import requests
from datetime import datetime, timezone

try:
    from deluge_client import DelugeRPCClient
except ImportError:
    DelugeRPCClient = None

# === Flask Setup ===
app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()

# === Config from environment ===
BASE_DIR = os.getenv("BASE_DIR", "/tv")
PROCESSED_DIR_FILE = os.getenv("PROCESSED_DIR_FILE", "/data/processed_directories.json")
PNG_FILE = os.getenv("PNG_FILE", "plex.png")

# Deluge
DELUGE_HOST = os.getenv("DELUGE_HOST", "localhost")
DELUGE_PORT = int(os.getenv("DELUGE_PORT", "58846"))
DELUGE_USER = os.getenv("DELUGE_USER", "localclient")
DELUGE_PASS = os.getenv("DELUGE_PASS", "")

# Sonarr
SONARR_URL = os.getenv("SONARR_URL", "http://localhost:8989")
SONARR_API_KEY = os.getenv("SONARR_API_KEY", "")
SONARR_MIN_AGE = int(os.getenv("SONARR_MIN_AGE", "120"))

VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi')

# === HTML Template ===
FORM_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head><title>TV Show Management</title></head>
<body>
    <h1>TV Show Management</h1>
    <form method="post" action="/manage">
        <label for="name">TV Show Name:</label>
        <input type="text" id="name" name="name" required>
        <button type="submit" name="action" value="search">Search</button>
    </form>
    <h2>Processed Directories</h2>
    <ul>
        {% for dir in directories %}
            <li>{{ dir }} <a href="/manage?action=remove&dir={{ dir }}">Remove</a></li>
        {% endfor %}
    </ul>
    {% if suggestions %}
        <h2>Did you mean:</h2>
        <ul>
            {% for suggestion in suggestions %}
                <li>{{ suggestion }}</li>
            {% endfor %}
        </ul>
    {% endif %}
</body>
</html>
'''


# === Helpers ===
def load_processed_directories():
    if os.path.exists(PROCESSED_DIR_FILE):
        with open(PROCESSED_DIR_FILE, 'r') as file:
            return json.load(file)
    return {}


def save_processed_directories(data):
    with open(PROCESSED_DIR_FILE, 'w') as file:
        json.dump(data, file)


processed_directories = load_processed_directories()


def find_tv_show_directory(show_name):
    matched_dir = None
    suggestions = []
    threshold = 0.6

    for root, dirs, _ in os.walk(BASE_DIR):
        for dir_name in dirs:
            similarity = difflib.SequenceMatcher(None, show_name.lower(), dir_name.lower()).ratio()
            if similarity == 1.0:
                return os.path.join(root, dir_name), []
            elif similarity >= threshold:
                suggestions.append(dir_name)
    return matched_dir, suggestions


def copy_png_to_videos(show_dir):
    for root, _, files in os.walk(show_dir):
        for video_file in files:
            if video_file.endswith(VIDEO_EXTENSIONS):
                video_name, _ = os.path.splitext(video_file)
                dest_png = os.path.join(root, f"{video_name}.png")
                if os.path.exists(PNG_FILE):
                    shutil.copy(PNG_FILE, dest_png)


def check_for_new_files():
    for show_dir in processed_directories.keys():
        copy_png_to_videos(show_dir)


# === Flask Routes ===
@app.route('/manage', methods=['GET', 'POST'])
def manage():
    global processed_directories

    if request.method == 'POST' and request.form.get('action') == 'search':
        show_name = request.form.get('name')
        show_dir, suggestions = find_tv_show_directory(show_name)
        if not show_dir:
            return render_template_string(FORM_TEMPLATE,
                                          directories=list(processed_directories.keys()),
                                          suggestions=suggestions)

        copy_png_to_videos(show_dir)
        processed_directories[show_dir] = True
        save_processed_directories(processed_directories)
        return redirect(url_for('manage'))

    if request.method == 'GET' and request.args.get('action') == 'remove':
        dir_to_remove = request.args.get('dir')
        if dir_to_remove in processed_directories:
            del processed_directories[dir_to_remove]
            save_processed_directories(processed_directories)
        return redirect(url_for('manage'))

    return render_template_string(FORM_TEMPLATE, directories=list(processed_directories.keys()))


# === Deluge Cleanup ===
def check_and_remove_torrents():
    if not DelugeRPCClient:
        print("Deluge client not installed.")
        return

    try:
        client = DelugeRPCClient(DELUGE_HOST, DELUGE_PORT, DELUGE_USER, DELUGE_PASS)
        client.connect()
    except Exception as e:
        print(f"Failed to connect to Deluge: {e}")
        return

    unwanted_exts = ['.zipx', '.mkv.lnk', '.arj', '.exe', '.001', '.gz', '.iso', '.scr']
    torrents = client.call('core.get_torrents_status', {}, [])

    for tid, tdata in torrents.items():
        label = tdata.get(b'label', b'').decode('utf-8', errors='ignore')
        if label.lower() != "tv-sonarr":
            continue

        files = tdata.get(b'files', [])
        if not files:
            client.call('core.remove_torrent', tid, True)
            continue
        for f in files:
            fname = f.get(b'path', b'').decode('utf-8', errors='ignore')
            if any(fname.endswith(ext) for ext in unwanted_exts):
                client.call('core.remove_torrent', tid, True)
                break


# === Sonarr Cleanup ===
def get_queue():
    url = f"{SONARR_URL}/api/v3/queue"
    headers = {"X-Api-Key": SONARR_API_KEY}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def delete_queue_item(item_id):
    url = f"{SONARR_URL}/api/v3/queue/{item_id}"
    headers = {"X-Api-Key": SONARR_API_KEY}
    requests.delete(url, headers=headers)


def parse_age(item):
    date_str = item.get("added")
    if not date_str:
        return 0
    added_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - added_time).total_seconds() / 60


def clear_queue():
    queue = get_queue()
    failed = []
    for item in queue.get("records", queue):
        status = item.get("status", "").lower()
        tracked = item.get("trackedDownloadStatus", "").lower()
        if any(k in status for k in ("failed", "warning")) or tracked in ("manual", "importfailed"):
            if parse_age(item) >= SONARR_MIN_AGE:
                failed.append(item["id"])

    for fid in failed:
        delete_queue_item(fid)
        print(f"Removed Sonarr queue item ID {fid}")


# === Scheduled Jobs ===
scheduler.add_job(check_for_new_files, trigger="interval", hours=24)
scheduler.add_job(check_and_remove_torrents, trigger="interval", hours=1)
scheduler.add_job(clear_queue, trigger="interval", minutes=10)

# === Entrypoint ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5555)

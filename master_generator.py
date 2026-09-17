import os
import time
import json
import requests
import google.generativeai as genai
from datetime import datetime
from moviepy.editor import VideoFileClip, concatenate_videoclips

# --- 1. SETUP KEYS ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
HF_TOKEN = os.environ.get("HF_TOKEN")

today_date = datetime.now().strftime("%d-%b-%Y")
file_date = datetime.now().strftime("%Y%m%d_%H%M")
vid_num = int(time.time())

# --- 2. HUGGING FACE T2V ---
def generate_t2v(prompt, filename):
    print(f"🎥 Generating Video for: {prompt}")
    # URL split to avoid markdown bugs
    part1 = "https://"
    part2 = "api-inference.huggingface.co/models/ali-vilab/text-to-video-ms-1.7b"
    API_URL = part1 + part2
    headers = {"Authorization": "Bearer " + HF_TOKEN}
    
    for attempt in range(4):
        res = requests.post(API_URL, headers=headers, json={"inputs": prompt})
        if res.status_code == 200:
            with open(filename, "wb") as f: 
                f.write(res.content)
            return True
        time.sleep(15)
    return False

# --- 3. MAIN WORKFLOW ---
print("🎬 Starting 35s Funny Snake USA Video Process...")
model = genai.GenerativeModel('gemini-1.5-flash')

# A. Script Generation (Funny Snakes, USA Style, 35s = ~75 words)
script_prompt = """Write a 35-second YouTube Shorts script for a USA audience reacting to a funny/crazy snake encounter (like India trends but American style). 
Length: Exactly 75 words.
Output STRICTLY as a JSON array of 3 objects.
Each object:
1. "narration": American English script line.
2. "visual": A 3-word English prompt for AI video generator.
Return ONLY raw JSON array."""

try:
    script_text = model.generate_content(script_prompt).text
    if script_text.startswith("```json"): script_text = script_text[7:-3]
    elif script_text.startswith("```"): script_text = script_text[3:-3]
    scenes = json.loads(script_text.strip())
except Exception as e:
    print(f"❌ Gemini Script Error: {e}")
    exit(1)

clip_files = []

# B. Generate & Merge Assets
for i, scene in enumerate(scenes):
    raw_vid = "raw_" + str(vid_num) + "_" + str(i) + ".mp4"
    aud_file = "aud_" + str(vid_num) + "_" + str(i) + ".mp3"
    clip_file = "clip_" + str(vid_num) + "_" + str(i) + ".mp4"
    
    # Generate Voice
    os.system('edge-tts --voice "en-US-ChristopherNeural" --text "' + scene["narration"] + '" --write-media ' + aud_file)
    
    # Generate Video & Loop it
    if generate_t2v(scene["visual"], raw_vid):
        os.system('ffmpeg -y -stream_loop -1 -i "' + raw_vid + '" -i "' + aud_file + '" -map 0:v:0 -map 1:a:0 -c:v libx264 -c:a aac -shortest "' + clip_file + '" -loglevel error')
        clip_files.append(VideoFileClip(clip_file))

final_video = "Funny_Snake_" + file_date + ".mp4"
if clip_files:
    concatenate_videoclips(clip_files).write_videofile(final_video, fps=24, codec="libx264", logger=None)
else:
    print("❌ No clips generated. Exiting.")
    exit(1)

# C. Generate Metadata (Title, Desc, Tags)
meta_prompt = "Generate for a funny snake reaction short: 1. Catchy Title (under 60 chars) 2. Two-line Description 3. 5 comma-separated tags. Format exactly as: TITLE|DESC|TAGS"
meta = model.generate_content(meta_prompt).text.split('|')
title = meta[0].strip() if len(meta) > 0 else "Crazy Snake Encounter! 🐍"
desc = meta[1].strip() if len(meta) > 1 else "You won't believe what happened! #shorts #snake"
tags = meta[2].strip() if len(meta) > 2 else "snake, funny, reaction, shorts, crazy"

# --- 4. DASHBOARD GENERATION (index.html) ---
history_file = "history.json"
history = []
if os.path.exists(history_file):
    try:
        with open(history_file, "r") as f: history = json.loads(f.read())
    except:
        pass

# Add new video to top of history
history.insert(0, {
    "file": final_video, "title": title, "desc": desc, "tags": tags, "date": today_date, "id": str(vid_num)
})

with open(history_file, "w") as f: 
    f.write(json.dumps(history))

# Build Clean HTML UI
html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>USA Snake Shorts Studio</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #121212; color: #ffffff; margin: 0; padding: 20px; text-align: center; }
        h1 { color: #00e676; margin-bottom: 5px; }
        p.subtitle { color: #aaa; margin-bottom: 30px; }
        .grid { display: flex; flex-wrap: wrap; justify-content: center; gap: 25px; }
        .card { background: #1e1e1e; padding: 20px; border-radius: 15px; width: 320px; box-shadow: 0 8px 20px rgba(0,0,0,0.5); border: 1px solid #333; text-align: left; }
        .date-badge { display: inline-block; background: #333; color: #00e676; padding: 5px 10px; border-radius: 5px; font-size: 12px; font-weight: bold; margin-bottom: 15px; }
        video { width: 100%; border-radius: 10px; background: #000; margin-bottom: 15px; }
        .btn-download { display: block; background: #00e676; color: #000; text-align: center; text-decoration: none; padding: 12px; font-weight: bold; border-radius: 8px; margin-bottom: 10px; transition: 0.3s; }
        .btn-download:hover { background: #00c853; }
        .btn-toggle { background: #333; color: #fff; width: 100%; border: none; padding: 12px; font-weight: bold; border-radius: 8px; cursor: pointer; transition: 0.3s; }
        .btn-toggle:hover { background: #444; }
        
        /* Details Section */
        .details-box { display: none; margin-top: 15px; background: #171717; padding: 15px; border-radius: 10px; border: 1px solid #2a2a2a; }
        .detail-row { margin-bottom: 15px; }
        .detail-row label { display: block; font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; font-weight: bold; }
        .copy-group { display: flex; align-items: stretch; background: #222; border-radius: 6px; overflow: hidden; border: 1px solid #333; }
        .copy-text { flex: 1; padding: 10px; font-size: 13px; color: #ddd; max-height: 60px; overflow-y: auto; word-wrap: break-word; }
        .copy-btn { background: #4285f4; border: none; color: white; padding: 0 15px; cursor: pointer; font-weight: bold; font-size: 12px; transition: 0.2s; }
        .copy-btn:hover { background: #3367d6; }
    </style>
</head>
<body>
    <h1>🐍 USA Viral Snake Studio</h1>
    <p class="subtitle">Daily AI Shorts | Ready to Download & Upload</p>
    <div class="grid">
"""

for item in history:
    v_id = item['id']
    html_content += f"""
        <div class="card">
            <div class="date-badge">📅 {item['date']}</div>
            <video src="{item['file']}" controls preload="metadata"></video>
            
            <a href="{item['file']}" download class="btn-download">⬇️ Download Video</a>
            <button class="btn-toggle" onclick="toggleDetails('{v_id}')">📝 Show Title & Tags</button>
            
            <div class="details-box" id="box-{v_id}">
                <div class="detail-row">
                    <label>Title</label>
                    <div class="copy-group">
                        <div class="copy-text" id="t-{v_id}">{item['title']}</div>
                        <button class="copy-btn" onclick="copyData('t-{v_id}')">COPY</button>
                    </div>
                </div>
                <div class="detail-row">
                    <label>Description</label>
                    <div class="copy-group">
                        <div class="copy-text" id="d-{v_id}">{item['desc']}</div>
                        <button class="copy-btn" onclick="copyData('d-{v_id}')">COPY</button>
                    </div>
                </div>
                <div class="detail-row">
                    <label>Tags</label>
                    <div class="copy-group">
                        <div class="copy-text" id="g-{v_id}">{item['tags']}</div>
                        <button class="copy-btn" onclick="copyData('g-{v_id}')">COPY</button>
                    </div>
                </div>
            </div>
        </div>
    """

html_content += """
    </div>

    <script>
        function toggleDetails(id) {
            let box = document.getElementById('box-' + id);
            box.style.display = (box.style.display === 'block') ? 'none' : 'block';
        }

        function copyData(elementId) {
            let textToCopy = document.getElementById(elementId).innerText;
            navigator.clipboard.writeText(textToCopy).then(() => {
                alert("Copied to clipboard! ✅");
            }).catch(err => {
                alert("Failed to copy text.");
            });
        }
    </script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f: 
    f.write(html_content)

print("🌐 Dashboard Updated Successfully!")

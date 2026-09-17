import os
import time
import json
import requests
from datetime import datetime
from moviepy.editor import VideoFileClip, concatenate_videoclips

# --- 1. SETUP KEYS ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN")

if not GEMINI_API_KEY or not HF_TOKEN:
    print("❌ Error: API Keys missing in GitHub Secrets!")
    exit(1)

today_date = datetime.now().strftime("%d-%b-%Y")

# --- 2. THE BULLETPROOF GEMINI API (NO PACKAGES NEEDED) ---
def ask_gemini(prompt):
    print("🧠 Contacting Gemini AI...")
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}
    
    try:
        res = requests.post(url, json=payload, headers=headers)
        data = res.json()
        if "candidates" in data:
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            print(f"❌ Gemini Error Response: {data}")
            return None
    except Exception as e:
        print(f"❌ Gemini Connection Error: {e}")
        return None

# --- 3. HUGGING FACE T2V (Crash-Proof) ---
def generate_t2v(prompt, filename):
    print(f"🎥 Generating Video for: {prompt}")
    part1 = "https://"
    part2 = "api-inference.huggingface.co/models/ali-vilab/text-to-video-ms-1.7b"
    API_URL = part1 + part2
    headers = {"Authorization": "Bearer " + HF_TOKEN}
    
    for attempt in range(4):
        try:
            res = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=60)
            if res.status_code == 200:
                with open(filename, "wb") as f: 
                    f.write(res.content)
                return True
            else:
                print(f"⚠️ HF Server Busy (Status {res.status_code}).")
        except Exception as e:
            print(f"⚠️ Network/Connection Error: {e}")
            
        print(f"⏳ Retrying... Attempt {attempt+1}/4")
        time.sleep(15)
    return False

# --- 4. STATE MANAGEMENT (PAUSE & RESUME LOGIC) ---
STATE_FILE = "video_state.json"
HISTORY_FILE = "history.json"
state = {}

if os.path.exists(STATE_FILE):
    print("🔄 Found incomplete video! Resuming from where we left yesterday...")
    try:
        with open(STATE_FILE, "r") as f:
            state = json.loads(f.read())
    except:
        pass

if not state:
    print("🎬 Starting NEW 35s Funny Snake USA Video Process...")
    vid_num = int(time.time())
    
    script_prompt = """Write a 35-second YouTube Shorts script for a USA audience reacting to a funny/crazy snake encounter (like India trends but American style). 
    Length: Exactly 75 words.
    Output STRICTLY as a JSON array of 3 objects.
    Each object:
    1. "narration": American English script line.
    2. "visual": A 3-word English prompt for AI video generator.
    Return ONLY raw JSON array."""

    script_text = ask_gemini(script_prompt)
    if not script_text:
        print("❌ Failed to get script. Exiting.")
        exit(1)
        
    if script_text.startswith("```json"): script_text = script_text[7:-3]
    elif script_text.startswith("```"): script_text = script_text[3:-3]
    
    try:
        scenes = json.loads(script_text.strip())
    except Exception as e:
        print(f"❌ JSON Parsing Error: {e}\nText: {script_text}")
        exit(1)

    meta_prompt = "Generate for a funny snake reaction short: 1. Catchy Title (under 60 chars) 2. Two-line Description 3. 5 comma-separated tags. Format exactly as: TITLE|DESC|TAGS"
    meta_text = ask_gemini(meta_prompt)
    
    try:
        meta = meta_text.split('|')
        title = meta[0].strip() if len(meta) > 0 else "Crazy Snake Encounter! 🐍"
        desc = meta[1].strip() if len(meta) > 1 else "You won't believe what happened! #shorts"
        tags = meta[2].strip() if len(meta) > 2 else "snake, funny, reaction, shorts, crazy"
    except:
        title, desc, tags = "Crazy Snake!", "Watch this!", "snake, funny"
        
    state = {
        "vid_num": vid_num,
        "scenes": scenes,
        "meta": {"title": title, "desc": desc, "tags": tags},
        "completed_clips": []
    }
    with open(STATE_FILE, "w") as f: f.write(json.dumps(state))

# --- 5. ASSET GENERATION LOOP (Resume Enabled) ---
scenes = state["scenes"]
vid_num = state["vid_num"]
completed = state["completed_clips"]

start_index = len(completed)

for i in range(start_index, len(scenes)):
    scene = scenes[i]
    raw_vid = "raw_" + str(vid_num) + "_" + str(i) + ".mp4"
    aud_file = "aud_" + str(vid_num) + "_" + str(i) + ".mp3"
    clip_file = "clip_" + str(vid_num) + "_" + str(i) + ".mp4"
    
    os.system('edge-tts --voice "en-US-ChristopherNeural" --text "' + scene["narration"] + '" --write-media ' + aud_file)
    
    if generate_t2v(scene["visual"], raw_vid):
        os.system('ffmpeg -y -stream_loop -1 -i "' + raw_vid + '" -i "' + aud_file + '" -map 0:v:0 -map 1:a:0 -c:v libx264 -c:a aac -shortest "' + clip_file + '" -loglevel error')
        completed.append(clip_file)
        
        # Save progress securely after every successful scene
        state["completed_clips"] = completed
        with open(STATE_FILE, "w") as f: f.write(json.dumps(state))
    else:
        print(f"⚠️ Hugging Face API Error/Limit hit. Saving partial progress for tomorrow.")
        break # Loop band, jitna bana hai utna hi jod kar dega!

# --- 6. MERGE WHAT WE HAVE ---
final_video = "Funny_Snake_" + str(vid_num) + ".mp4"
is_complete = len(completed) == len(scenes)

if len(completed) > 0:
    print(f"🔗 Merging {len(completed)} clips...")
    clip_objs = [VideoFileClip(c) for c in completed]
    concatenate_videoclips(clip_objs).write_videofile(final_video, fps=24, codec="libx264", logger=None)
else:
    print("❌ No clips could be generated today. Wait for next day.")
    exit(0)

# --- 7. UPDATE DASHBOARD HISTORY ---
history = []
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r") as f: history = json.loads(f.read())
    except: pass

# Replace old partial video entry with updated one
history = [h for h in history if h.get("id") != str(vid_num)]

status_text = "Complete" if is_complete else f"Partial"

history.insert(0, {
    "file": final_video, 
    "title": state["meta"]["title"], 
    "desc": state["meta"]["desc"], 
    "tags": state["meta"]["tags"], 
    "date": today_date, 
    "id": str(vid_num),
    "status": status_text,
    "progress": f"{len(completed)}/{len(scenes)} Scenes"
})

with open(HISTORY_FILE, "w") as f: f.write(json.dumps(history))

if is_complete:
    if os.path.exists(STATE_FILE): os.remove(STATE_FILE)
    print("✅ VIDEO 100% COMPLETE!")
else:
    print(f"⏸️ VIDEO PARTIAL ({len(completed)}/{len(scenes)}). Will resume next day.")

# --- 8. BUILD HTML UI ---
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
        .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .date-badge { background: #333; color: #00e676; padding: 5px 10px; border-radius: 5px; font-size: 12px; font-weight: bold; }
        
        .status-complete { background: #133320; color: #00ff66; padding: 5px 10px; border-radius: 5px; font-size: 11px; font-weight: bold; border: 1px solid #00ff66; }
        .status-partial { background: #332600; color: #ffcc00; padding: 5px 10px; border-radius: 5px; font-size: 11px; font-weight: bold; border: 1px solid #ffcc00; animation: blink 1.5s infinite; }
        @keyframes blink { 50% { opacity: 0.6; } }

        video { width: 100%; border-radius: 10px; background: #000; margin-bottom: 15px; }
        .btn-download { display: block; background: #00e676; color: #000; text-align: center; text-decoration: none; padding: 12px; font-weight: bold; border-radius: 8px; margin-bottom: 10px; transition: 0.3s; }
        .btn-download:hover { background: #00c853; }
        .btn-toggle { background: #333; color: #fff; width: 100%; border: none; padding: 12px; font-weight: bold; border-radius: 8px; cursor: pointer; transition: 0.3s; }
        .btn-toggle:hover { background: #444; }
        
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
    <p class="subtitle">Auto-Pause & Resume Supported | Safe from Errors</p>
    <div class="grid">
"""

for item in history:
    v_id = item['id']
    is_done = item['status'] == 'Complete'
    
    stat_class = "status-complete" if is_done else "status-partial"
    stat_text = "🟢 100% Complete" if is_done else f"⏳ {item['progress']} (Wait next day)"
    
    html_content += f"""
        <div class="card">
            <div class="header-row">
                <div class="date-badge">📅 {item['date']}</div>
                <div class="{stat_class}">{stat_text}</div>
            </div>
            
            <video src="{item['file']}" controls preload="metadata"></video>
            
            <a href="{item['file']}" download class="btn-download">⬇️ Download {"Complete " if is_done else "Partial "}Video</a>
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

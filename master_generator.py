import os
import time
import json
import requests
from datetime import datetime
from moviepy.editor import VideoFileClip, concatenate_videoclips

# --- 1. SETUP KEYS & MULTI-TOKENS ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Smart Token Fetcher (Reads HF_TOKEN, HF_TOKEN2... up to HF_TOKEN30)
hf_tokens = []
for i in range(1, 31):
    key_name = "HF_TOKEN" if i == 1 else f"HF_TOKEN{i}"
    t_val = os.environ.get(key_name)
    if t_val: hf_tokens.append(t_val)

if not GEMINI_API_KEY or not hf_tokens:
    print("❌ Error: API Keys or HF Tokens missing in GitHub Secrets!")
    exit(1)

print(f"🔑 Successfully loaded {len(hf_tokens)} Hugging Face Tokens!")
today_date = datetime.now().strftime("%d-%b-%Y")
RUN_MODE = os.environ.get("RUN_MODE", "FULL") 

# --- 2. THE ULTIMATE GEMINI AI (YOUR HTML METHOD) ---
def ask_gemini(prompt):
    print("🧠 Contacting Gemini AI...")
    url = "https://generativelanguage.googleapis.com/v1beta/interactions"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }
    payload = {
        "model": "gemini-3.6-flash",
        "input": [
            {
                "type": "user_input",
                "content": [{"type": "text", "text": prompt}]
            }
        ],
        "store": False
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers)
        data = res.json()
        
        text_output = ""
        if data and "steps" in data:
            for step in data["steps"]:
                if step.get("type") == "model_output":
                    for item in step.get("content", []):
                        if item.get("type") == "text": 
                            text_output += item.get("text", "")
                            
        if text_output:
            print("✅ Gemini API Success!")
            return text_output.strip()
        else:
            print(f"❌ Gemini Error Response: {data}")
            return None
            
    except Exception as e:
        print(f"❌ Gemini Connection Error: {e}")
        return None

# --- 3. HUGGING FACE T2V (AUTO-SWITCHING MAGIC) ---
def generate_t2v(prompt, filename):
    print(f"🎥 Generating Video for: {prompt}")
    API_URL = "https://api-inference.huggingface.co/models/ali-vilab/text-to-video-ms-1.7b"
    
    for idx, token in enumerate(hf_tokens):
        token_name = "HF_TOKEN" if idx == 0 else f"HF_TOKEN{idx+1}"
        print(f"🔄 Trying with {token_name}...")
        headers = {"Authorization": "Bearer " + token}
        
        for attempt in range(2): # Try 2 times per token
            try:
                res = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=60)
                if res.status_code == 200:
                    with open(filename, "wb") as f: f.write(res.content)
                    print(f"✅ Success with {token_name}!")
                    return True
                elif res.status_code == 429:
                    print(f"⚠️ Limit hit for {token_name}. Switching token...")
                    break # Break attempt loop, jump to next token
            except: pass
            time.sleep(10)
            
    print("❌ All Hugging Face Tokens exhausted!")
    return False

# --- 4. STATE MANAGEMENT ---
STATE_FILE = "video_state.json"
HISTORY_FILE = "history.json"
state = {}

if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f: state = json.loads(f.read())
    except: pass

if not state:
    print("🎬 Generating New Script for Today...")
    vid_num = int(time.time())
    script_prompt = """Write a 35-second YouTube Shorts script for a USA audience reacting to a funny/crazy snake encounter. Length: Exactly 75 words. Output STRICTLY as a JSON array of 3 objects. 1. "narration": American English script line. 2. "visual": A 3-word English prompt for AI video. Return ONLY raw JSON array."""
    
    script_text = ask_gemini(script_prompt)
    
    if script_text:
        if script_text.startswith("```json"): script_text = script_text[7:-3]
        elif script_text.startswith("```"): script_text = script_text[3:-3]
        
        try:
            scenes = json.loads(script_text.strip())
        except Exception as e:
            print(f"❌ JSON Parse Error: {e}\nRaw Text: {script_text}")
            exit(1)
    else:
        print("❌ Failed to load script. Exiting.")
        exit(1)

    meta_text = ask_gemini("Generate for funny snake reaction short: 1. Catchy Title (<60 chars) 2. 2-line Description 3. 5 comma-separated tags. Format: TITLE|DESC|TAGS")
    try:
        meta = meta_text.split('|')
        title, desc, tags = meta[0].strip(), meta[1].strip(), meta[2].strip()
    except:
        title, desc, tags = "Crazy Snake! 🐍", "Must watch! #shorts", "snake, funny, reaction"
        
    state = {"vid_num": vid_num, "scenes": scenes, "meta": {"title": title, "desc": desc, "tags": tags}, "completed_clips": []}
    with open(STATE_FILE, "w") as f: f.write(json.dumps(state))

scenes = state["scenes"]
vid_num = state["vid_num"]
completed = state["completed_clips"]
tokens_exhausted = False

if RUN_MODE == "DEMO":
    if len(completed) >= 1:
        print("⏳ Demo already done. Exiting.")
        exit(0)
    target_scenes = [scenes[0]]
else:
    target_scenes = scenes

start_index = len(completed)

for i in range(start_index, len(target_scenes)):
    scene = target_scenes[i]
    raw_vid, aud_file, clip_file = f"raw_{vid_num}_{i}.mp4", f"aud_{vid_num}_{i}.mp3", f"clip_{vid_num}_{i}.mp4"
    os.system(f'edge-tts --voice "en-US-ChristopherNeural" --text "{scene["narration"]}" --write-media {aud_file}')
    
    if generate_t2v(scene["visual"], raw_vid):
        os.system(f'ffmpeg -y -stream_loop -1 -i "{raw_vid}" -i "{aud_file}" -map 0:v:0 -map 1:a:0 -c:v libx264 -c:a aac -shortest "{clip_file}" -loglevel error')
        completed.append(clip_file)
        state["completed_clips"] = completed
        with open(STATE_FILE, "w") as f: f.write(json.dumps(state))
    else:
        tokens_exhausted = True
        break

# --- 5. MERGE & DASHBOARD UPDATE ---
final_video = f"Funny_Snake_{vid_num}.mp4"
is_complete = len(completed) == len(scenes)

if len(completed) > 0:
    clip_objs = [VideoFileClip(c) for c in completed]
    concatenate_videoclips(clip_objs).write_videofile(final_video, fps=24, codec="libx264", logger=None)
else:
    print("❌ No clips generated.")
    exit(1)

history = []
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r") as f: history = json.loads(f.read())
    except: pass

history = [h for h in history if h.get("id") != str(vid_num)]

if is_complete:
    status_msg = "🟢 100% Complete"
    status_type = "done"
elif tokens_exhausted:
    status_msg = "❌ All Tokens Empty! (Wait next day)"
    status_type = "err"
else:
    status_msg = f"⏳ Demo Ready (Making Full Tonight...)"
    status_type = "demo"

history.insert(0, {
    "file": final_video, "title": state["meta"]["title"], "desc": state["meta"]["desc"], 
    "tags": state["meta"]["tags"], "date": today_date, "id": str(vid_num),
    "status_msg": status_msg, "status_type": status_type
})

with open(HISTORY_FILE, "w") as f: f.write(json.dumps(history))

if is_complete and os.path.exists(STATE_FILE): os.remove(STATE_FILE)

# --- 6. HTML UI ---
html = """<!DOCTYPE html><html lang="en"><head><title>USA Snake Studio</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
    body { font-family: sans-serif; background: #121212; color: #fff; margin: 0; padding: 20px; text-align: center; }
    h1 { color: #00e676; } .grid { display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; }
    .card { background: #1e1e1e; padding: 20px; border-radius: 15px; width: 320px; border: 1px solid #333; text-align: left; }
    .head { display: flex; justify-content: space-between; margin-bottom: 10px; }
    .date { background: #333; color: #00e676; padding: 4px 8px; border-radius: 5px; font-size: 12px; font-weight: bold; }
    .stat-demo { background: #332600; color: #ffcc00; padding: 4px 8px; border-radius: 5px; font-size: 11px; font-weight: bold; animation: blink 1s infinite; }
    .stat-done { background: #133320; color: #00ff66; padding: 4px 8px; border-radius: 5px; font-size: 11px; font-weight: bold; }
    .stat-err { background: #331313; color: #ff4d4d; padding: 4px 8px; border-radius: 5px; font-size: 11px; font-weight: bold; }
    @keyframes blink { 50% { opacity: 0.5; } }
    video { width: 100%; border-radius: 10px; background: #000; margin-bottom: 10px; }
    .btn { background: #00e676; color: #000; display: block; padding: 10px; text-decoration: none; text-align: center; font-weight: bold; border-radius: 6px; margin-bottom: 5px; cursor: pointer; border: none; width: 100%; box-sizing: border-box; }
    .btn-dark { background: #333; color: #fff; }
    .box { display: none; background: #171717; padding: 10px; border-radius: 8px; margin-top: 10px; font-size: 12px; }
    .row { display: flex; margin-bottom: 5px; border-radius: 4px; overflow: hidden; }
    .txt { background: #222; padding: 8px; flex: 1; overflow-y: auto; max-height: 50px; }
    .cpy { background: #4285f4; color: white; border: none; padding: 0 10px; cursor: pointer; font-weight: bold; }
</style></head><body><h1>🐍 Live USA Snake Studio</h1><div class="grid">"""

for h in history:
    v_id = h['id']
    c_stat = f"stat-{h['status_type']}"
    html += f"""<div class="card"><div class="head"><div class="date">📅 {h['date']}</div><div class="{c_stat}">{h['status_msg']}</div></div>
    <video src="{h['file']}" controls></video>
    <a href="{h['file']}" download class="btn">⬇️ Download {"Full" if h['status_type'] == "done" else "Demo"} Video</a>
    <button class="btn btn-dark" onclick="document.getElementById('b-{v_id}').style.display = document.getElementById('b-{v_id}').style.display === 'block' ? 'none' : 'block'">📝 Show Title & Tags</button>
    <div class="box" id="b-{v_id}">
        <div class="row"><div class="txt" id="t-{v_id}">{h['title']}</div><button class="cpy" onclick="navigator.clipboard.writeText(document.getElementById('t-{v_id}').innerText)">COPY</button></div>
        <div class="row"><div class="txt" id="d-{v_id}">{h['desc']}</div><button class="cpy" onclick="navigator.clipboard.writeText(document.getElementById('d-{v_id}').innerText)">COPY</button></div>
        <div class="row"><div class="txt" id="g-{v_id}">{h['tags']}</div><button class="cpy" onclick="navigator.clipboard.writeText(document.getElementById('g-{v_id}').innerText)">COPY</button></div>
    </div></div>"""

html += "</div></body></html>"
with open("index.html", "w") as f: f.write(html)
print("🌐 Webpage Updated Successfully!")

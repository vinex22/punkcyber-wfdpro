"""
WFD Pro Clock - Web UI Controller
A Flask web interface for the WFD Pro 7x7 LED matrix clock.
"""

import json
import os
import threading
import time as _time
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
import psutil
from wfd_clock import WFDClock, DISPLAY_MODES, make_frame, heart_pattern, blank_matrix, full_matrix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MATRIX_DIR = os.path.join(BASE_DIR, 'matrix')

app = Flask(__name__)
clock = WFDClock()

# ── 3x5 pixel font for digits 0-9 (each digit is 5 rows × 3 cols) ──────────
DIGIT_FONT = {
    0: [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
    1: [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
    2: [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]],
    3: [[1,1,1],[0,0,1],[1,1,1],[0,0,1],[1,1,1]],
    4: [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]],
    5: [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
    6: [[1,1,1],[1,0,0],[1,1,1],[1,0,1],[1,1,1]],
    7: [[1,1,1],[0,0,1],[0,0,1],[0,0,1],[0,0,1]],
    8: [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,1,1]],
    9: [[1,1,1],[1,0,1],[1,1,1],[0,0,1],[1,1,1]],
}

# Label indicators (tiny 7x7 patterns with a letter + value)
LABEL_FONT = {
    'C': [[1,1,1],[1,0,0],[1,0,0],[1,0,0],[1,1,1]],  # CPU
    'G': [[1,1,1],[1,0,0],[1,0,1],[1,0,1],[1,1,1]],  # GPU
    'M': [[1,0,1],[1,1,1],[1,1,1],[1,0,1],[1,0,1]],  # MEM
}


def render_percent_on_matrix(value, label=None):
    """Render a 0-99 percentage value on a 7x7 LED matrix.
    If label is provided ('C','G','M'), show label letter in top 2 rows
    and value below. Otherwise show 2-digit number centered.
    """
    value = max(0, min(99, int(value)))
    tens = value // 10
    ones = value % 10

    matrix = [[0]*7 for _ in range(7)]

    # Two 3x5 digits side-by-side with 1px gap = 7px wide, 5px tall
    # Place at row 1..5 (centered vertically in 7 rows)
    d1 = DIGIT_FONT[tens]
    d2 = DIGIT_FONT[ones]
    row_offset = 1
    for r in range(5):
        for c in range(3):
            matrix[row_offset + r][c] = d1[r][c]      # left digit cols 0-2
            matrix[row_offset + r][c + 4] = d2[r][c]  # right digit cols 4-6

    # Top row: label indicator dot pattern
    if label and label in LABEL_FONT:
        # Show small 3-pixel label marker centered on row 0
        if label == 'C':
            matrix[0] = [0, 1, 0, 0, 0, 1, 0]  # dots for C(pu)
        elif label == 'G':
            matrix[0] = [0, 0, 1, 0, 1, 0, 0]  # dots for G(pu)
        elif label == 'M':
            matrix[0] = [1, 0, 1, 0, 1, 0, 1]  # dots for M(em)

    return matrix


# ── System monitor auto-send thread ─────────────────────────────────────────
monitor_state = {
    'running': False,
    'interval': 3,
    'mode': 'cpu',  # cpu, gpu, memory, cycle
    'cpu': 0,
    'gpu': 0,
    'memory': 0,
}
_monitor_thread = None
_monitor_stop = threading.Event()


def _get_gpu_usage():
    """Get GPU usage via Windows performance counters (works for Intel/AMD/NVIDIA)."""
    try:
        import subprocess
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "(Get-Counter '\\GPU Engine(*engtype_3D)\\Utilization Percentage' -ErrorAction SilentlyContinue).CounterSamples | Measure-Object CookedValue -Sum | Select-Object -ExpandProperty Sum"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            val = float(result.stdout.strip())
            return max(0, min(100, int(val)))
    except Exception:
        pass
    return 0


def _monitor_loop():
    """Background loop that reads system stats and sends to clock bar display."""
    while not _monitor_stop.is_set():
        try:
            monitor_state['cpu'] = int(psutil.cpu_percent(interval=0))
            monitor_state['gpu'] = _get_gpu_usage()
            monitor_state['memory'] = int(psutil.virtual_memory().percent)

            if clock.ser and clock.ser.is_open:
                clock.send_system_stats(
                    monitor_state['cpu'],
                    monitor_state['memory'],
                    monitor_state['gpu'],
                )
        except Exception:
            pass

        _monitor_stop.wait(monitor_state['interval'])


def start_monitor():
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        return
    _monitor_stop.clear()
    monitor_state['running'] = True
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()


def stop_monitor():
    global _monitor_thread
    _monitor_stop.set()
    monitor_state['running'] = False
    if _monitor_thread:
        _monitor_thread.join(timeout=5)
        _monitor_thread = None

# ── HTML Template ────────────────────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WFD Pro Clock</title>
<style>
  :root {
    --bg: #0f1117; --card: #1a1d27; --accent: #6c5ce7; --accent2: #a29bfe;
    --text: #e0e0e0; --text2: #888; --border: #2a2d3a; --green: #00b894;
    --red: #e17055; --orange: #fdcb6e;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }

  .container { max-width:900px; margin:0 auto; padding:24px 16px; }

  header { text-align:center; margin-bottom:32px; }
  header h1 { font-size:28px; font-weight:700; letter-spacing:1px; }
  header h1 span { color:var(--accent2); }
  header p { color:var(--text2); font-size:14px; margin-top:4px; }

  .status-bar { display:flex; align-items:center; justify-content:center; gap:12px; margin:16px 0; padding:12px; background:var(--card); border-radius:10px; border:1px solid var(--border); }
  .status-dot { width:10px; height:10px; border-radius:50%; background:var(--red); flex-shrink:0; }
  .status-dot.connected { background:var(--green); }
  #statusText { font-size:14px; color:var(--text2); }

  .connection-row { display:flex; gap:10px; justify-content:center; flex-wrap:wrap; margin-bottom:24px; }
  select, button, input { font-family:inherit; font-size:14px; border:none; outline:none; border-radius:8px; }
  select { background:var(--card); color:var(--text); padding:10px 14px; border:1px solid var(--border); min-width:200px; }
  select:focus { border-color:var(--accent); }

  .btn { padding:10px 20px; font-weight:600; cursor:pointer; transition:all .15s; }
  .btn-primary { background:var(--accent); color:#fff; }
  .btn-primary:hover { background:var(--accent2); }
  .btn-success { background:var(--green); color:#fff; }
  .btn-success:hover { opacity:.85; }
  .btn-danger  { background:var(--red); color:#fff; }
  .btn-danger:hover { opacity:.85; }
  .btn-outline { background:transparent; color:var(--accent2); border:1px solid var(--accent2); }
  .btn-outline:hover { background:var(--accent2); color:#fff; }
  .btn:disabled { opacity:.4; cursor:default; }

  .grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:24px; }
  @media (max-width:600px) { .grid { grid-template-columns:1fr; } }

  .card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; }
  .card h3 { font-size:15px; color:var(--accent2); margin-bottom:14px; text-transform:uppercase; letter-spacing:.5px; }

  .control-row { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
  .control-row label { font-size:14px; color:var(--text2); }
  .control-row .val { font-size:14px; font-weight:600; min-width:32px; text-align:center; }

  input[type=range] { -webkit-appearance:none; width:160px; height:6px; border-radius:3px; background:var(--border); }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:18px; height:18px; border-radius:50%; background:var(--accent); cursor:pointer; }

  .radio-group { display:flex; gap:8px; flex-wrap:wrap; }
  .radio-group label { padding:6px 14px; border-radius:6px; background:var(--bg); border:1px solid var(--border); cursor:pointer; font-size:13px; transition:all .15s; }
  .radio-group input { display:none; }
  .radio-group input:checked+span { color:var(--accent2); }
  .radio-group label:has(input:checked) { border-color:var(--accent); background:rgba(108,92,231,.15); }

  .time-inputs { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  .time-inputs input[type=time] { background:var(--bg); color:var(--text); border:1px solid var(--border); padding:6px 10px; border-radius:6px; }

  /* LED Matrix Editor */
  .matrix-section { margin-top:24px; }
  .matrix-wrap { display:flex; flex-direction:column; align-items:center; gap:16px; }
  .matrix-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:4px; }
  .led { width:42px; height:42px; border-radius:8px; background:var(--bg); border:2px solid var(--border); cursor:pointer; transition:all .15s; }
  .led.on { background:var(--accent); border-color:var(--accent2); box-shadow:0 0 12px rgba(108,92,231,.5); }
  .led:hover { border-color:var(--accent2); }
  .matrix-controls { display:flex; gap:8px; flex-wrap:wrap; justify-content:center; }

  .frame-bar { display:flex; gap:8px; align-items:center; justify-content:center; margin-top:8px; flex-wrap:wrap; }
  .frame-bar .frame-tab { padding:6px 12px; border-radius:6px; background:var(--bg); border:1px solid var(--border); cursor:pointer; font-size:13px; }
  .frame-bar .frame-tab.active { border-color:var(--accent); background:rgba(108,92,231,.15); color:var(--accent2); }

  .speed-row { display:flex; align-items:center; gap:10px; margin-top:8px; }
  .speed-row label { font-size:13px; color:var(--text2); }

  .log-box { background:var(--bg); border:1px solid var(--border); border-radius:8px; padding:12px; margin-top:16px; max-height:160px; overflow-y:auto; font-family:'Cascadia Code',monospace; font-size:12px; color:var(--green); line-height:1.6; }
  .log-box .err { color:var(--red); }

  .quick-actions { display:flex; gap:8px; flex-wrap:wrap; justify-content:center; margin-bottom:24px; }

  /* System Monitor */
  .monitor-card { grid-column:1/-1; }
  .stats-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:16px; }
  .stat-box { background:var(--bg); border:1px solid var(--border); border-radius:8px; padding:14px; text-align:center; }
  .stat-box .stat-label { font-size:12px; color:var(--text2); text-transform:uppercase; margin-bottom:4px; }
  .stat-box .stat-value { font-size:28px; font-weight:700; }
  .stat-box .stat-value.cpu { color:#6c5ce7; }
  .stat-box .stat-value.gpu { color:#00b894; }
  .stat-box .stat-value.mem { color:#fdcb6e; }
  .stat-bar { height:4px; border-radius:2px; background:var(--border); margin-top:8px; overflow:hidden; }
  .stat-bar-fill { height:100%; border-radius:2px; transition:width .3s; }
  .stat-bar-fill.cpu { background:#6c5ce7; }
  .stat-bar-fill.gpu { background:#00b894; }
  .stat-bar-fill.mem { background:#fdcb6e; }
  .monitor-controls { display:flex; gap:10px; align-items:center; flex-wrap:wrap; justify-content:center; }
  .monitor-controls select { min-width:120px; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>&#x1F4A1; WFD <span>Pro</span> Clock</h1>
    <p>7&times;7 LED Matrix Controller</p>
  </header>

  <!-- Status -->
  <div class="status-bar">
    <div class="status-dot" id="statusDot"></div>
    <span id="statusText">Disconnected</span>
  </div>

  <!-- Connection -->
  <div class="connection-row">
    <select id="portSelect"><option value="">Loading ports...</option></select>
    <button class="btn btn-primary" onclick="refreshPorts()">Refresh</button>
    <button class="btn btn-success" id="connectBtn" onclick="toggleConnect()">Connect</button>
  </div>

  <!-- Quick Actions -->
  <div class="quick-actions">
    <button class="btn btn-outline" onclick="apiPost('/api/sync_time')">&#x1F552; Sync Time</button>
    <button class="btn btn-outline" onclick="apiPost('/api/request_params')">&#x1F4E5; Read Params</button>
    <button class="btn btn-outline" onclick="sendPreset('heart')">&#x2764;&#xFE0F; Heart</button>
    <button class="btn btn-outline" onclick="sendPreset('full')">&#x2B1C; Full</button>
    <button class="btn btn-outline" onclick="sendPreset('blank')">&#x2B1B; Clear</button>
  </div>

  <!-- Animation Library -->
  <div class="card" style="margin-bottom:24px;">
    <h3>&#x1F3AC; Animation Library</h3>
    <div id="animLibrary" style="display:flex;gap:8px;flex-wrap:wrap;">Loading...</div>
    <div style="margin-top:12px;display:flex;gap:8px;align-items:center;">
      <input type="file" id="animUpload" accept=".json" style="display:none;" onchange="uploadAnim(this)">
      <button class="btn btn-outline" onclick="document.getElementById('animUpload').click()">&#x1F4E4; Upload Animation</button>
      <span id="uploadStatus" style="font-size:13px;color:var(--text2);"></span>
    </div>
  </div>

  <!-- Controls Grid -->
  <div class="grid">
    <!-- Brightness -->
    <div class="card">
      <h3>Brightness</h3>
      <div class="control-row">
        <label>Level</label>
        <input type="range" id="brightness" min="1" max="4" value="2" oninput="document.getElementById('brightVal').textContent=this.value" onchange="apiPost('/api/brightness',{level:+this.value})">
        <span class="val" id="brightVal">2</span>
      </div>
    </div>

    <!-- Sensitivity -->
    <div class="card">
      <h3>Sensitivity</h3>
      <div class="control-row">
        <label>Level</label>
        <input type="range" id="sensitivity" min="1" max="5" value="3" oninput="document.getElementById('sensVal').textContent=this.value" onchange="apiPost('/api/sensitivity',{level:+this.value})">
        <span class="val" id="sensVal">3</span>
      </div>
    </div>

    <!-- Display Mode -->
    <div class="card">
      <h3>Display Mode</h3>
      <div class="radio-group">
        <label><input type="radio" name="dispMode" value="1" onchange="apiPost('/api/display_mode',{mode:1})"><span>Bottom→Top</span></label>
        <label><input type="radio" name="dispMode" value="2" onchange="apiPost('/api/display_mode',{mode:2})"><span>Top→Bottom</span></label>
        <label><input type="radio" name="dispMode" value="3" onchange="apiPost('/api/display_mode',{mode:3})"><span>Center→Sides</span></label>
        <label><input type="radio" name="dispMode" value="4" onchange="apiPost('/api/display_mode',{mode:4})"><span>Sides→Center</span></label>
      </div>
    </div>

    <!-- Hour Mode -->
    <div class="card">
      <h3>Hour Format</h3>
      <div class="radio-group">
        <label><input type="radio" name="hourMode" value="12" onchange="apiPost('/api/hour_mode',{mode:'12h'})"><span>12 Hour</span></label>
        <label><input type="radio" name="hourMode" value="24" onchange="apiPost('/api/hour_mode',{mode:'24h'})"><span>24 Hour</span></label>
      </div>
    </div>

    <!-- Night Mode -->
    <div class="card" style="grid-column:1/-1;">
      <h3>Night Mode</h3>
      <div class="time-inputs">
        <label style="color:var(--text2);font-size:13px;">Start</label>
        <input type="time" id="nightStart" value="23:00">
        <label style="color:var(--text2);font-size:13px;">End</label>
        <input type="time" id="nightEnd" value="07:00">
        <button class="btn btn-outline" onclick="setNightMode()">Set</button>
        <button class="btn btn-danger" style="padding:8px 14px;font-size:13px;" onclick="apiPost('/api/night_mode',{start_hour:0,start_min:0,end_hour:0,end_min:0})">Disable</button>
      </div>
    </div>

    <!-- System Monitor -->
    <div class="card monitor-card">
      <h3>System Monitor → Clock</h3>
      <div class="stats-grid">
        <div class="stat-box">
          <div class="stat-label">CPU</div>
          <div class="stat-value cpu" id="cpuVal">0%</div>
          <div class="stat-bar"><div class="stat-bar-fill cpu" id="cpuBar" style="width:0%"></div></div>
        </div>
        <div class="stat-box">
          <div class="stat-label">GPU</div>
          <div class="stat-value gpu" id="gpuVal">0%</div>
          <div class="stat-bar"><div class="stat-bar-fill gpu" id="gpuBar" style="width:0%"></div></div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Memory</div>
          <div class="stat-value mem" id="memVal">0%</div>
          <div class="stat-bar"><div class="stat-bar-fill mem" id="memBar" style="width:0%"></div></div>
        </div>
      </div>
      <div class="monitor-controls">
        <label style="color:var(--text2);font-size:13px;">Interval</label>
        <input type="range" id="monitorInterval" min="1" max="10" value="3" style="width:100px;" oninput="document.getElementById('intVal').textContent=this.value+'s'">
        <span class="val" id="intVal">3s</span>
        <button class="btn btn-success" id="monitorBtn" onclick="toggleMonitor()">Start</button>
        <button class="btn btn-outline" onclick="sendStatOnce()">Send Once</button>
      </div>
    </div>
  </div>

  <!-- LED Matrix Editor -->
  <div class="card matrix-section">
    <h3>LED Matrix Editor</h3>
    <div class="matrix-wrap">
      <div class="matrix-grid" id="matrixGrid"></div>
      <div class="matrix-controls">
        <button class="btn btn-outline" onclick="clearMatrix()">Clear</button>
        <button class="btn btn-outline" onclick="fillMatrix()">Fill All</button>
        <button class="btn btn-outline" onclick="invertMatrix()">Invert</button>
        <button class="btn btn-primary" onclick="sendMatrix()">&#x1F680; Send to Clock</button>
      </div>
      <div class="speed-row">
        <label>Frame duration:</label>
        <input type="range" id="timeSlot" min="1" max="20" value="5" oninput="document.getElementById('tsVal').textContent=this.value">
        <span class="val" id="tsVal">5</span>
      </div>
    </div>
  </div>

  <!-- Log -->
  <div class="log-box" id="logBox"></div>
</div>

<script>
let connected = false;
const matrix = Array.from({length:7}, ()=>Array(7).fill(0));

// ── Init matrix grid ──
(function initGrid(){
  const grid = document.getElementById('matrixGrid');
  for(let r=0;r<7;r++) for(let c=0;c<7;c++){
    const d=document.createElement('div');
    d.className='led';
    d.dataset.r=r; d.dataset.c=c;
    d.addEventListener('click',()=>toggleLed(r,c,d));
    grid.appendChild(d);
  }
})();

function toggleLed(r,c,el){
  matrix[r][c] = matrix[r][c]?0:1;
  el.classList.toggle('on');
}
function clearMatrix(){
  for(let r=0;r<7;r++) for(let c=0;c<7;c++) matrix[r][c]=0;
  refreshGrid();
}
function fillMatrix(){
  for(let r=0;r<7;r++) for(let c=0;c<7;c++) matrix[r][c]=1;
  refreshGrid();
}
function invertMatrix(){
  for(let r=0;r<7;r++) for(let c=0;c<7;c++) matrix[r][c]=matrix[r][c]?0:1;
  refreshGrid();
}
function refreshGrid(){
  const leds=document.querySelectorAll('.led');
  leds.forEach(el=>{
    const r=+el.dataset.r, c=+el.dataset.c;
    el.classList.toggle('on', !!matrix[r][c]);
  });
}

// ── API helpers ──
function log(msg, isErr){
  const box=document.getElementById('logBox');
  const line=document.createElement('div');
  if(isErr) line.className='err';
  line.textContent='> '+msg;
  box.appendChild(line);
  box.scrollTop=box.scrollHeight;
}

async function apiPost(url, body={}){
  try{
    const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await res.json();
    if(data.ok) log(data.message||'OK');
    else log(data.error||'Error','err');
    return data;
  }catch(e){ log('Request failed: '+e.message,true); }
}

async function refreshPorts(){
  try{
    const res=await fetch('/api/ports');
    const data=await res.json();
    const sel=document.getElementById('portSelect');
    sel.innerHTML='';
    if(!data.ports.length){
      sel.innerHTML='<option value="">No ports found</option>';
      return;
    }
    data.ports.forEach(([dev,desc])=>{
      const o=document.createElement('option');
      o.value=dev; o.textContent=dev+' - '+desc;
      sel.appendChild(o);
    });
  }catch(e){ log('Failed to list ports: '+e.message,true); }
}

async function toggleConnect(){
  if(connected){
    const data=await apiPost('/api/disconnect');
    if(data&&data.ok) setConnected(false);
  }else{
    const port=document.getElementById('portSelect').value;
    if(!port){ log('Select a port first','err'); return; }
    const data=await apiPost('/api/connect',{port});
    if(data&&data.ok) setConnected(true);
  }
}

function setConnected(val){
  connected=val;
  document.getElementById('statusDot').classList.toggle('connected',val);
  document.getElementById('statusText').textContent=val?'Connected':'Disconnected';
  const btn=document.getElementById('connectBtn');
  btn.textContent=val?'Disconnect':'Connect';
  btn.className='btn '+(val?'btn-danger':'btn-success');
}

function setNightMode(){
  const s=document.getElementById('nightStart').value.split(':');
  const e=document.getElementById('nightEnd').value.split(':');
  apiPost('/api/night_mode',{start_hour:+s[0],start_min:+s[1],end_hour:+e[0],end_min:+e[1]});
}

function sendMatrix(){
  const ts=+document.getElementById('timeSlot').value;
  apiPost('/api/send_frame',{frames:[{data:matrix,time_slot:ts}]});
}

function sendPreset(name){
  apiPost('/api/preset',{name});
}

// ── System Monitor ──
let monitorActive = false;
let statsPollTimer = null;

function pollStats(){
  fetch('/api/stats').then(r=>r.json()).then(data=>{
    document.getElementById('cpuVal').textContent=data.cpu+'%';
    document.getElementById('gpuVal').textContent=data.gpu+'%';
    document.getElementById('memVal').textContent=data.memory+'%';
    document.getElementById('cpuBar').style.width=data.cpu+'%';
    document.getElementById('gpuBar').style.width=data.gpu+'%';
    document.getElementById('memBar').style.width=data.memory+'%';
  }).catch(()=>{});
}

async function toggleMonitor(){
  if(monitorActive){
    await apiPost('/api/monitor/stop');
    monitorActive=false;
    if(statsPollTimer) clearInterval(statsPollTimer);
    statsPollTimer=null;
    document.getElementById('monitorBtn').textContent='Start';
    document.getElementById('monitorBtn').className='btn btn-success';
  }else{
    const interval=+document.getElementById('monitorInterval').value;
    const data=await apiPost('/api/monitor/start',{interval});
    if(data&&data.ok){
      monitorActive=true;
      document.getElementById('monitorBtn').textContent='Stop';
      document.getElementById('monitorBtn').className='btn btn-danger';
      pollStats();
      statsPollTimer=setInterval(pollStats, 2000);
    }
  }
}

async function sendStatOnce(){
  await apiPost('/api/monitor/send_once');
  pollStats();
}

// ── Animation Library ──
async function loadAnimLibrary(){
  try{
    const res=await fetch('/api/animations');
    const data=await res.json();
    const container=document.getElementById('animLibrary');
    container.innerHTML='';
    if(!data.animations.length){ container.textContent='No animations found'; return; }
    data.animations.forEach(a=>{
      const btn=document.createElement('button');
      btn.className='btn btn-outline';
      btn.textContent=a.name+' ('+a.frames+'f)';
      btn.onclick=()=>sendAnimation(a.file);
      container.appendChild(btn);
    });
  }catch(e){ console.error(e); }
}

async function sendAnimation(file){
  await apiPost('/api/send_animation',{file});
}

async function uploadAnim(input){
  const file=input.files[0];
  if(!file) return;
  const status=document.getElementById('uploadStatus');
  status.textContent='Uploading...';
  const formData=new FormData();
  formData.append('file',file);
  try{
    const res=await fetch('/api/upload_animation',{method:'POST',body:formData});
    const data=await res.json();
    if(data.ok){ status.textContent='Uploaded: '+file.name; loadAnimLibrary(); }
    else status.textContent='Error: '+(data.error||'Upload failed');
  }catch(e){ status.textContent='Upload failed: '+e.message; }
  input.value='';
}

// init
refreshPorts();
statsPollTimer=setInterval(pollStats, 3000);
pollStats();
loadAnimLibrary();
</script>
</body>
</html>
"""


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/api/ports')
def api_ports():
    ports = WFDClock.list_ports()
    return jsonify({"ports": ports})


@app.route('/api/connect', methods=['POST'])
def api_connect():
    data = request.get_json(force=True)
    port = data.get('port')
    if not port:
        return jsonify({"ok": False, "error": "No port specified"}), 400
    try:
        clock.connect(port)
        return jsonify({"ok": True, "message": f"Connected to {port}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    try:
        clock.disconnect()
        return jsonify({"ok": True, "message": "Disconnected"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/sync_time', methods=['POST'])
def api_sync_time():
    try:
        clock.sync_time()
        return jsonify({"ok": True, "message": f"Time synced: {datetime.now().strftime('%H:%M:%S')}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/brightness', methods=['POST'])
def api_brightness():
    data = request.get_json(force=True)
    level = int(data.get('level', 2))
    try:
        clock.set_brightness(level)
        return jsonify({"ok": True, "message": f"Brightness → {level}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/sensitivity', methods=['POST'])
def api_sensitivity():
    data = request.get_json(force=True)
    level = int(data.get('level', 3))
    try:
        clock.set_sensitivity(level)
        return jsonify({"ok": True, "message": f"Sensitivity → {level}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/display_mode', methods=['POST'])
def api_display_mode():
    data = request.get_json(force=True)
    mode = int(data.get('mode', 1))
    try:
        clock.set_display_mode(mode)
        return jsonify({"ok": True, "message": f"Display mode → {DISPLAY_MODES.get(mode, '?')}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/hour_mode', methods=['POST'])
def api_hour_mode():
    data = request.get_json(force=True)
    mode = data.get('mode', '24h')
    try:
        clock.set_hour_mode(mode == '12h')
        return jsonify({"ok": True, "message": f"Hour mode → {mode}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/night_mode', methods=['POST'])
def api_night_mode():
    data = request.get_json(force=True)
    sh = int(data.get('start_hour', 0))
    sm = int(data.get('start_min', 0))
    eh = int(data.get('end_hour', 0))
    em = int(data.get('end_min', 0))
    try:
        clock.set_night_mode(sh, sm, eh, em)
        if sh == 0 and sm == 0 and eh == 0 and em == 0:
            msg = "Night mode disabled"
        else:
            msg = f"Night mode → {sh:02d}:{sm:02d} - {eh:02d}:{em:02d}"
        return jsonify({"ok": True, "message": msg})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/send_frame', methods=['POST'])
def api_send_frame():
    data = request.get_json(force=True)
    frames = data.get('frames', [])
    if not frames:
        return jsonify({"ok": False, "error": "No frames provided"}), 400
    try:
        frame_dicts = [{"data": f["data"], "time_slot": f.get("time_slot", 5)} for f in frames]
        clock.send_animation(frame_dicts)
        return jsonify({"ok": True, "message": f"Sent {len(frame_dicts)} frame(s)"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/preset', methods=['POST'])
def api_preset():
    data = request.get_json(force=True)
    name = data.get('name', '')
    presets = {
        'heart': heart_pattern(),
        'full': full_matrix(),
        'blank': blank_matrix(),
    }
    pattern = presets.get(name)
    if not pattern:
        return jsonify({"ok": False, "error": f"Unknown preset: {name}"}), 400
    try:
        clock.send_animation([make_frame(pattern, 10)])
        return jsonify({"ok": True, "message": f"Sent preset: {name}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/request_params', methods=['POST'])
def api_request_params():
    try:
        clock.request_params()
        return jsonify({"ok": True, "message": "Requested device params (check serial log)"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── System monitor endpoints ─────────────────────────────────────────────────

@app.route('/api/stats')
def api_stats():
    cpu = int(psutil.cpu_percent(interval=0))
    gpu = _get_gpu_usage()
    mem = int(psutil.virtual_memory().percent)
    monitor_state['cpu'] = cpu
    monitor_state['gpu'] = gpu
    monitor_state['memory'] = mem
    return jsonify({"cpu": cpu, "gpu": gpu, "memory": mem, "monitor_running": monitor_state['running']})


@app.route('/api/monitor/start', methods=['POST'])
def api_monitor_start():
    data = request.get_json(force=True)
    monitor_state['mode'] = data.get('mode', 'cycle')
    monitor_state['interval'] = max(1, min(10, int(data.get('interval', 3))))
    start_monitor()
    return jsonify({"ok": True, "message": f"Monitor started: {monitor_state['mode']} every {monitor_state['interval']}s"})


@app.route('/api/monitor/stop', methods=['POST'])
def api_monitor_stop():
    stop_monitor()
    return jsonify({"ok": True, "message": "Monitor stopped"})


@app.route('/api/monitor/send_once', methods=['POST'])
def api_monitor_send_once():
    try:
        monitor_state['cpu'] = int(psutil.cpu_percent(interval=0))
        monitor_state['gpu'] = _get_gpu_usage()
        monitor_state['memory'] = int(psutil.virtual_memory().percent)

        clock.send_system_stats(
            monitor_state['cpu'],
            monitor_state['memory'],
            monitor_state['gpu'],
        )
        return jsonify({"ok": True, "message": f"Stats sent: CPU={monitor_state['cpu']}% MEM={monitor_state['memory']}% GPU={monitor_state['gpu']}%"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Animation library endpoints ──────────────────────────────────────────────

@app.route('/api/upload_animation', methods=['POST'])
def api_upload_animation():
    if 'file' not in request.files:
        return jsonify({"ok": False, "error": "No file provided"}), 400
    f = request.files['file']
    if not f.filename or not f.filename.endswith('.json'):
        return jsonify({"ok": False, "error": "Only .json files allowed"}), 400
    # Sanitize filename
    import re
    safe_name = re.sub(r'[^\w\u4e00-\u9fff\-.]', '_', f.filename)
    if not safe_name:
        return jsonify({"ok": False, "error": "Invalid filename"}), 400
    os.makedirs(MATRIX_DIR, exist_ok=True)
    fpath = os.path.join(MATRIX_DIR, safe_name)
    try:
        content = f.read()
        # Validate it's proper animation JSON
        frames = json.loads(content)
        if not isinstance(frames, list) or not frames:
            return jsonify({"ok": False, "error": "JSON must be an array of frames"}), 400
        for frame in frames:
            if 'data' not in frame or len(frame['data']) != 7:
                return jsonify({"ok": False, "error": "Each frame must have 'data' with 7 rows"}), 400
        with open(fpath, 'wb') as out:
            out.write(content)
        return jsonify({"ok": True, "message": f"Uploaded {safe_name} ({len(frames)} frames)"})
    except json.JSONDecodeError:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/animations')
def api_animations():
    anims = []
    if os.path.isdir(MATRIX_DIR):
        for fname in sorted(os.listdir(MATRIX_DIR)):
            if fname.endswith('.json'):
                fpath = os.path.join(MATRIX_DIR, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        frames = json.load(f)
                    name = os.path.splitext(fname)[0]
                    anims.append({"name": name, "file": fname, "frames": len(frames)})
                except Exception:
                    pass
    return jsonify({"animations": anims})


@app.route('/api/send_animation', methods=['POST'])
def api_send_animation():
    data = request.get_json(force=True)
    fname = data.get('file', '')
    # sanitize: only allow filenames, no path traversal
    if not fname or os.sep in fname or '/' in fname or '..' in fname:
        return jsonify({"ok": False, "error": "Invalid filename"}), 400
    fpath = os.path.join(MATRIX_DIR, fname)
    if not os.path.isfile(fpath):
        return jsonify({"ok": False, "error": f"File not found: {fname}"}), 404
    try:
        clock.send_animation_file(fpath)
        return jsonify({"ok": True, "message": f"Sent animation: {fname}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == '__main__':
    # prime psutil cpu_percent
    psutil.cpu_percent(interval=0)
    print("Starting WFD Pro Clock Web UI...")
    print("Open http://localhost:5000 in your browser")
    app.run(host='127.0.0.1', port=5000, debug=False)

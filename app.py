import json
import os
import re
import threading
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA_DIR = os.environ.get("DATA_DIR", "/data" if os.path.isdir("/data") else "./data")
FILE = os.path.join(DATA_DIR, "cigs.json")
PORT = int(os.environ.get("PORT", "8080"))
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_lock = threading.Lock()

os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(FILE):
    with open(FILE, "w") as f:
        json.dump({}, f)

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>cigs</title>
<style>
:root{--fg:#24292f;--muted:#57606a;--faint:#8c959f;--border:#d0d7de;--l0:#ebedf0;--l1:#9be9a8;--l2:#40c463;--l3:#30a14e;--l4:#216e39}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--fg);font:14px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
main{max-width:760px;margin:0 auto;padding:28px 16px 56px}
header{display:flex;align-items:baseline;justify-content:space-between}
h1{margin:0;font-size:15px;font-weight:600;letter-spacing:.02em}
h1 a{color:var(--faint);text-decoration:none;font-weight:400;font-size:12px}
h1 a:hover{color:var(--muted)}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0 22px}
.stats>div{border:1px solid var(--border);border-radius:6px;padding:10px 12px}
.stats b{display:block;font-size:20px;font-weight:600;font-variant-numeric:tabular-nums}
.stats span{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.press{display:flex;align-items:center;justify-content:center;gap:14px;margin:0 0 26px}
#cig{background:var(--fg);color:#fff;border:0;border-radius:8px;padding:13px 34px;font-size:16px;font-weight:600;font-family:inherit;cursor:pointer;user-select:none;-webkit-user-select:none;touch-action:manipulation}
#cig:hover{background:#3a424b}
#cig:active{transform:scale(.97)}
#undo{background:none;border:0;color:var(--faint);font:12px/1 inherit;cursor:pointer;text-decoration:underline;text-underline-offset:3px;padding:6px}
#undo:hover{color:var(--muted)}
#undo:disabled{color:#d0d7de;cursor:default}
.views{display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.seg{display:flex;border:1px solid var(--border);border-radius:6px;overflow:hidden}
.seg button{background:none;border:0;padding:5px 14px;font:12px/1 inherit;color:var(--muted);cursor:pointer}
.seg button.on{background:var(--fg);color:#fff}
.nav{margin-left:auto;display:flex;align-items:center;gap:6px}
.nav button{background:none;border:1px solid var(--border);border-radius:6px;width:26px;height:26px;color:var(--muted);cursor:pointer;font-size:13px;line-height:1}
.nav button:hover:not(:disabled){border-color:var(--fg);color:var(--fg)}
.nav button:disabled{opacity:.35;cursor:default}
.nav b{font-size:14px;font-weight:600;min-width:150px;text-align:center;font-variant-numeric:tabular-nums}
#wrap{overflow-x:auto;padding-bottom:4px}
#grid{position:relative;user-select:none;-webkit-user-select:none}
.cell{position:absolute;border-radius:2px;cursor:pointer}
.cell:hover{outline:1px solid var(--fg);outline-offset:0}
.cell.today{box-shadow:inset 0 0 0 1px var(--fg)}
.wdl{position:absolute;font-size:9px;color:var(--faint)}
.ml{position:absolute;font-size:10px;color:var(--muted);white-space:nowrap}
footer{margin-top:26px;color:var(--faint);font-size:12px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
footer a{color:var(--muted)}
.legend{display:flex;align-items:center;gap:3px;margin-left:auto;font-size:10px;color:var(--faint)}
.legend i{width:10px;height:10px;border-radius:2px;display:inline-block}
@media(max-width:560px){.stats{grid-template-columns:repeat(2,1fr)}.nav b{min-width:120px}}
</style>
</head>
<body>
<main>
<header><h1>cigs</h1><a href="/export">export csv</a></header>
<div class="stats">
  <div><b id="s-today">–</b><span>today</span></div>
  <div><b id="s-total">–</b><span>total</span></div>
  <div><b id="s-avg">–</b><span>weekly avg</span></div>
  <div><b id="s-sd">–</b><span>weekly σ</span></div>
</div>
<div class="press"><button id="cig">+ cig</button><button id="undo" disabled>undo</button></div>
<div class="views">
  <div class="seg"><button id="v-month" class="on">Month</button><button id="v-year">Year</button></div>
  <div class="nav"><button id="prev" title="back">‹</button><b id="label"></b><button id="next" title="forward">›</button></div>
</div>
<div id="wrap"><div id="grid"></div></div>
<footer><span id="f-note"></span>
  <div class="legend">less <i style="background:var(--l0)"></i><i style="background:var(--l1)"></i><i style="background:var(--l2)"></i><i style="background:var(--l3)"></i><i style="background:var(--l4)"></i> more</div>
</footer>
</main>
<script>
const $=s=>document.querySelector(s);
const DAY=86400000;
const LVL=c=>c? c<5?1: c<10?2: c<15?3:4 :0;
const COLORS=['var(--l0)','var(--l1)','var(--l2)','var(--l3)','var(--l4)'];
const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
const WD=['M','T','W','T','F','S','S'];
let DATES=[];
let view={mode:'month',y:new Date().getFullYear(),m:new Date().getMonth()};

const counts=()=>DATES;
const utc=(y,m,d)=>Date.UTC(y,m,d);
const monday=t=>{const d=new Date(t).getUTCDay();return t-((d+6)%7)*DAY};
const fmt=t=>new Date(t).toISOString().slice(0,10);
const todayStr=()=>{const d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')};

async function refresh(){
  DATES=await(await fetch('/api/dates')).json();
  renderStats();
  renderHeatmap();
  $('#undo').disabled=!Object.keys(DATES).length;
}

async function post(path,body){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
  if(!r.ok){const e=await r.json().catch(()=>({}));alert(e.error||'error');return}
  await refresh();
}

function renderStats(){
  const c=counts(),today=todayStr();
  const total=Object.values(c).reduce((a,b)=>a+b,0);
  $('#s-today').textContent=c[today]||0;
  $('#s-total').textContent=total;
  $('#f-note').textContent=total? total+' cigs since '+Object.keys(c).sort()[0] :'no cigs logged yet';
  if(!total){$('#s-avg').textContent='–';$('#s-sd').textContent='–';return}
  const s0=Object.keys(c).sort()[0].split('-').map(Number);
  const t0=today.split('-').map(Number);
  const start=monday(utc(s0[0],s0[1]-1,s0[2]));
  const end=monday(utc(t0[0],t0[1]-1,t0[2]));
  const weeks=[];
  for(let w=start;w<=end;w+=7*DAY){
    let s=0;
    for(let d=0;d<7;d++){const k=fmt(w+d*DAY);if(c[k])s+=c[k]}
    weeks.push(s);
  }
  const avg=weeks.reduce((a,b)=>a+b,0)/weeks.length;
  const sd=Math.sqrt(weeks.reduce((a,b)=>a+(b-avg)**2,0)/weeks.length);
  $('#s-avg').textContent=avg.toFixed(1);
  $('#s-sd').textContent=sd.toFixed(1);
}

function renderHeatmap(){
  const g=$('#grid');g.innerHTML='';
  const c=counts(),now=new Date();
  const nowMid=utc(now.getFullYear(),now.getMonth(),now.getDate());
  const big=view.mode==='month';
  const size=big?17:12,gap=big?4:3,pitch=size+gap,pl=16,pt=big?0:16;

  let start,end;
  if(big){
    start=monday(utc(view.y,view.m,1));
    end=monday(utc(view.y,view.m+1,0))+6*DAY;
  }else{
    start=monday(utc(view.y,0,1));
    end=monday(utc(view.y,11,31))+6*DAY;
  }
  const cols=Math.round((end-start)/DAY/7)+1;
  const weeksOf=[];
  for(let i=0;i<cols;i++)weeksOf.push(start+i*7*DAY);

  WD.forEach((w,r)=>{const e=document.createElement('i');e.className='wdl';e.textContent=w;e.style.cssText='left:0;top:'+(pt+r*pitch+(size-(big?12:9))/2)+'px';g.appendChild(e)});

  if(!big)MONTHS.forEach((m,i)=>{
    const i1=utc(view.y,i,1);
    if(i1<start||i1>end)return;
    const idx=Math.round((monday(i1)-start)/DAY/7);
    const e=document.createElement('i');e.className='ml';e.textContent=m.slice(0,3);
    e.style.left=(pl+idx*pitch)+'px';e.style.top='0';g.appendChild(e);
  });

  for(let w=0;w<weeksOf.length;w++)for(let d=0;d<7;d++){
    const t=weeksOf[w]+d*DAY;
    if(big&&(t<utc(view.y,view.m,1)||t>utc(view.y,view.m+1,0)))continue;
    if(!big&&t>nowMid)continue;
    const k=fmt(t),n=c[k]||0;
    const e=document.createElement('i');
    e.className='cell'+(k===todayStr()?' today':'');
    e.style.cssText='left:'+(pl+w*pitch)+'px;top:'+(pt+d*pitch)+'px;width:'+size+'px;height:'+size+'px;background:'+COLORS[LVL(n)];
    e.title=k+' — '+(n?n+(n===1?' cigarette':' cigarettes'):'none')+' (click to add, shift-click / hold to remove)';
    e.onclick=ev=>ev.shiftKey?post('/api/remove',{date:k}):post('/api/log',{date:k});
    e.oncontextmenu=ev=>{ev.preventDefault();post('/api/remove',{date:k})};
    e.dataset.hold='0';
    e.addEventListener('touchstart',()=>{e.dataset.hold='0';e._t=setTimeout(()=>{e.dataset.hold='1';post('/api/remove',{date:k})},550)},{passive:true});
    e.addEventListener('touchend',()=>clearTimeout(e._t));
    g.appendChild(e);
  }
  g.style.width=(pl+weeksOf.length*pitch)+'px';
  g.style.height=(pt+7*pitch)+'px';
}

function clampNav(){
  const ks=Object.keys(DATES);
  const y0=ks.length?+ks.sort()[0].slice(0,4):view.y;
  $('#prev').disabled=view.mode==='month'? view.y*12+view.m<=+y0*12 : view.y<=y0;
  const n=new Date();
  $('#next').disabled=view.mode==='month'? view.y*12+view.m>=n.getFullYear()*12+n.getMonth() : view.y>=n.getFullYear();
}

function syncLabel(){
  $('#label').textContent=view.mode==='month'?MONTHS[view.m]+' '+view.y:view.y;
}

$('#cig').onclick=()=>post('/api/log',{date:todayStr()});
$('#undo').onclick=()=>post('/api/undo');
$('#v-month').onclick=()=>{view.mode='month';$('#v-month').classList.add('on');$('#v-year').classList.remove('on');syncLabel();clampNav();renderHeatmap()};
$('#v-year').onclick=()=>{view.mode='year';$('#v-year').classList.add('on');$('#v-month').classList.remove('on');syncLabel();clampNav();renderHeatmap()};
$('#prev').onclick=()=>{if(view.mode==='month'){view.m--;if(view.m<0){view.m=11;view.y--}}else view.y--;syncLabel();clampNav();renderHeatmap()};
$('#next').onclick=()=>{if(view.mode==='month'){view.m++;if(view.m>11){view.m=0;view.y++}}else view.y++;syncLabel();clampNav();renderHeatmap()};

refresh().then(()=>{syncLabel();clampNav()});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _file(self):
        with _lock, open(FILE) as f:
            return json.load(f)

    def _save(self, data):
        with _lock:
            tmp = FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f)
            os.replace(tmp, FILE)

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _log(self, msg):
        pass  # quiet access logs

    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/dates":
            data = self._file()
            self._json(200, {d: len(v) for d, v in data.items()})
        elif self.path == "/export":
            lines = ["date,count"]
            for d in sorted(self._file()):
                lines.append(f"{d},{len(self._file()[d])}")
            body = "\n".join(lines).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", 'attachment; filename="cigs.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "bad json"})

        data = self._file()

        if self.path == "/api/log":
            if "date" in body:
                d = body["date"]
                if not (isinstance(d, str) and DATE_RE.match(d)):
                    return self._json(400, {"error": "bad date"})
                try:
                    # +1d slack: browser-local date can sit up to a day ahead of UTC
                    if date.fromisoformat(d) > date.today() + timedelta(days=1):
                        return self._json(400, {"error": "no future dates"})
                except ValueError:
                    return self._json(400, {"error": "bad date"})
            else:
                d = date.today().isoformat()
            data.setdefault(d, []).append(datetime.now().isoformat(timespec="seconds"))
            self._save(data)
            self._json(200, {"date": d, "count": len(data[d])})

        elif self.path == "/api/undo":
            newest = max((s for v in data.values() for s in v), default=None)
            if newest is None:
                return self._json(200, {"removed": None})
            d = newest[:10]
            data[d].remove(newest)
            if not data[d]:
                del data[d]
            self._save(data)
            self._json(200, {"removed": newest})

        elif self.path == "/api/remove":
            d = body.get("date", "")
            if not (isinstance(d, str) and DATE_RE.match(d) and data.get(d)):
                return self._json(404, {"error": "nothing to remove"})
            data[d].sort()
            data[d].pop()
            if not data[d]:
                del data[d]
            self._save(data)
            self._json(200, {"date": d, "count": len(data.get(d, []))})

        else:
            self.send_error(404)


if __name__ == "__main__":
    print(f"listening on :{PORT}, data in {FILE}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

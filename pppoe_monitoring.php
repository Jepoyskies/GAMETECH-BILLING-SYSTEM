<?php
include 'header.php';
?>

<style>
body {
    font-family: 'Segoe UI', 'Arial', sans-serif;
    background: linear-gradient(135deg, #eef2ff, #f8fafc);
    color: #0f172a;
    margin: 0;
    padding: 14px;
    min-height: 100vh;
    transition: background 0.4s, color 0.4s;
}
h2 {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 1.5em;
    margin-bottom: 18px;
}
@media (max-width: 600px) {
    h2 { font-size: 1.1em; }
}

/* LIVE DOT */
.live-dot {
    width: 10px;
    height: 10px;
    background: #22c55e;
    border-radius: 50%;
    animation: pulse 1.5s infinite;
    flex-shrink: 0;
}
@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.7); }
    70% { box-shadow: 0 0 0 10px rgba(34,197,94,0); }
}

/* TOPBAR */
.topbar {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 18px;
}
.topbar input,
.topbar select {
    flex: 1;
    min-width: 120px;
    padding: 10px;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    background: #ffffffcc;
    font-size: 1em;
    transition: border .2s;
}
.topbar input:focus, .topbar select:focus {
    border: 1.5px solid #3b82f6;
    outline: none;
}

/* SUMMARY */
.summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px;
    margin-bottom: 20px;
}
.box {
    padding: 18px 16px 12px 16px;
    border-radius: 20px;
    color: white;
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 20px rgba(0,0,0,0.08);
    transition: 0.25s;
    min-height: 120px;
    cursor: pointer;
}
.box:hover {
    transform: translateY(-4px) scale(1.03);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}
.box.rx { background: linear-gradient(135deg, #3b82f6 60%, #2563eb 100%); }
.box.tx { background: linear-gradient(135deg, #10b981 60%, #059669 100%); }
.box.net { background: linear-gradient(135deg, #8b5cf6 60%, #7c3aed 100%); }
.box.users { background: linear-gradient(135deg, #f59e0b 60%, #d97706 100%); }
.box.top { background: linear-gradient(135deg, #ef4444 60%, #dc2626 100%); }

.box h3 {
    margin: 0 0 4px 0;
    font-size: 13px;
    letter-spacing: 0.02em;
    opacity: 0.85;
    color: #fff;
}
.box p {
    margin: 6px 0 0;
    font-size: 23px;
    font-weight: bold;
    color: #fff;
    transition: color .2s;
}

.gauge-canvas {
    width: 62px !important;
    height: 62px !important;
    position: absolute;
    top: 14px;
    right: 10px;
    background: transparent;
    pointer-events: none;
}

/* USER CARDS */
#users {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 15px;
}
.card {
    padding: 14px 16px 10px 16px;
    border-radius: 17px;
    background: #fff;
    border: 1px solid #e2e8f0;
    transition: 0.22s;
    position: relative;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    display: flex;
    flex-direction: column;
    gap: 0.5em;
}
.card:hover {
    transform: translateY(-5px) scale(1.014);
    box-shadow: 0 6px 18px #3b82f63a;
}
.card.heavy {
    border: 2px solid #dc2626;
    background: linear-gradient(135deg, #fff1f2, #fff);
    animation: blink 1.2s infinite;
}
@keyframes blink {
    0%,100% { box-shadow: 0 0 0 #dc2626; }
    50% { box-shadow: 0 0 12px #dc2626; }
}
.card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 2px;
}
.card .username {
    font-weight: bold;
    color: #2563eb;
    font-size: 1.08em;
    letter-spacing: 0.01em;
    word-break: break-all;
    line-height: 1.2;
}
.card .ip {
    color: #7c3aed;
    font-size: 0.93em;
    margin-left: 7px;
    opacity: 0.7;
}
.card .speed-row {
    display: flex;
    align-items: center;
    gap: 13px;
    margin: 5px 0 1px 0;
}
.card .speed-number {
    display: flex;
    align-items: center;
    font-size: 1.2em;
    font-weight: bold;
    margin-right: 5px;
    color: #10b981;
}
.card .speed-number.download {
    color: #2563eb;
}
.card .speed-icon {
    font-size: 1.11em;
    margin-right: 2px;
}
.card .stat-label {
    font-size: 0.98em;
    color: #64748b;
    margin-right: 9px;
}
.speed-badge {
    position: absolute;
    top: 12px;
    right: 12px;
    color: #fff;
    font-size: 11px;
    padding: 4px 9px;
    border-radius: 8px;
    font-weight: 600;
    background: #16a34a;
    cursor: help;
    box-shadow: 0 2px 6px #0001;
}
.card .legend {
    position: absolute;
    bottom: 10px;
    right: 18px;
    font-size: 10px;
    background: #f8fafcdd;
    color: #222;
    border-radius: 8px;
    padding: 1px 6px;
    display: flex;
    gap: 8px;
    align-items: center;
}
.card .legend span {
    display: inline-block;
    width: 11px;
    height: 3px;
    border-radius: 2px;
    margin-right: 3px;
    vertical-align: middle;
}
.card .legend .ul { background: #2563eb; }
.card .legend .dl { background: #10b981; }

.user-graph-canvas {
    margin-top: 8px;
    width: 100%;
    height: 62px;
    background: transparent;
    border-radius: 7px;
    border: none;
    display: block;
    position: relative;
}

/* MOBILE NAVIGATION */
.mobile-nav {
    display: none;
}
@media (max-width: 600px) {
    .summary {
        grid-template-columns: 1fr 1fr;
    }
    #users { grid-template-columns: 1fr; }
    .mobile-nav {
        display: flex;
        position: fixed;
        left: 0; right: 0; bottom: 0;
        background: #fff;
        border-top: 1px solid #e2e8f0;
        z-index: 30;
        height: 58px;
        align-items: center;
        justify-content: space-around;
        padding: 0 8px;
        box-shadow: 0px -2px 12px rgba(0,0,0,0.03);
    }
    .mobile-nav button {
        background: none;
        border: none;
        font-size: 1.7em;
        color: #2563eb;
        padding: 0;
        margin: 0 12px;
        cursor: pointer;
        outline: none;
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    .mobile-nav .label {
        font-size: 12px;
        color: #64748b;
    }
    body { padding-bottom: 72px; }
}

::-webkit-scrollbar { width: 7px; background: transparent;}
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 6px;}
</style>

<h2>
    <span class="live-dot"></span>
    Live Monitoring
</h2>

<div class="topbar">
    <input type="text" id="search" placeholder="Search PPPoE user...">
    <select id="interval">
        <option value="1000">1s</option>
        <option value="5000" selected>5s</option>
    </select>
</div>

<div class="summary">
    <div class="box rx" title="Total upload from all users">
        <h3>Upload</h3>
        <p id="totalRx">0</p>
        <canvas class="gauge-canvas" id="gauge-rx" width="62" height="62"></canvas>
    </div>
    <div class="box tx" title="Total download from all users">
        <h3>Download</h3>
        <p id="totalTx">0</p>
        <canvas class="gauge-canvas" id="gauge-tx" width="62" height="62"></canvas>
    </div>
    <div class="box net" title="Upload + Download">
        <h3>Total Bandwidth</h3>
        <p id="totalNet">0</p>
        <canvas class="gauge-canvas" id="gauge-net" width="62" height="62"></canvas>
    </div>
    <div class="box users" title="Active PPPoE users online">
        <h3>Active Users</h3>
        <p id="activeUsers">0</p>
    </div>
    <div class="box top" title="Top user by bandwidth">
        <h3>Top User</h3>
        <p id="topUser">-</p>
    </div>
</div>

<div id="users">🔍 Start typing to search users...</div>

<nav class="mobile-nav" id="mobileNav">
    <button onclick="window.scrollTo({top:0,behavior:'smooth'})">
        <span>🏠</span>
        <span class="label">Summary</span>
    </button>
    <button onclick="document.getElementById('search').focus()">
        <span>🔍</span>
        <span class="label">Search</span>
    </button>
</nav>

<script>
let allData = [];
let history = {}; // {user: {rx:[], tx:[]}}
let timer = null;
let maxRx = 100, maxTx = 100, maxNet = 200; // Gauge scaling
let heavyMap = {}; // user => true if heavy

// --- GAUGE ---
function drawGauge(canvas, value, max, color) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0,0,w,h);
    let pct = Math.min(value/max, 1.0), r = 27, cx = w/2, cy = h/2;

    // background
    ctx.beginPath();
    ctx.arc(cx,cy,r,0,2*Math.PI);
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 8;
    ctx.stroke();

    // arc
    ctx.beginPath();
    ctx.arc(cx,cy,r,-Math.PI/2,-Math.PI/2 + pct*2*Math.PI);
    ctx.strokeStyle = color;
    ctx.lineWidth = 8;
    ctx.lineCap = 'round';
    ctx.stroke();

    // value
    ctx.font = "bold 15px Segoe UI";
    ctx.fillStyle = color;
    ctx.textAlign = "center";
    ctx.fillText(value.toFixed(1), cx, cy+4);
}

// --- ANIMATION ---
function animateValue(el, start, end, unit=" Mbps") {
    let duration = 400;
    let startTime = null;
    function step(t) {
        if (!startTime) startTime = t;
        let p = Math.min((t - startTime)/duration,1);
        let val = start + (end - start)*p;
        el.innerText = val.toFixed(2) + unit;
        if(p<1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

// --- GRAPH WITH RX & TX, LEGEND, GRID, HEAVY USER MARK ---
// SWAPPED: blue = Upload (rx), green = Download (tx)
function drawGraph(canvas, rxData, txData, isHeavy) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.offsetWidth;
    const h = canvas.height = 62;
    ctx.clearRect(0,0,w,h);
    if(rxData.length<2 && txData.length<2) return;

    // Background grid
    ctx.save();
    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.8;
    for(let i=1; i<=3; ++i) {
        let y = h*i/4;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
    }
    ctx.restore();

    // Find max for scaling
    const max = Math.max(...rxData, ...txData, 1);

    // Draw RX (Upload) - blue
    ctx.beginPath();
    rxData.forEach((v,i)=>{
        const x=(i/(rxData.length-1||1))*w;
        const y=h-(v/max)*h;
        i?ctx.lineTo(x,y):ctx.moveTo(x,y);
    });
    ctx.strokeStyle="#2563eb";
    ctx.lineWidth = 2.3;
    ctx.shadowColor = "#2563eb44";
    ctx.shadowBlur = 2;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Draw TX (Download) - green
    ctx.beginPath();
    txData.forEach((v,i)=>{
        const x=(i/(txData.length-1||1))*w;
        const y=h-(v/max)*h;
        i?ctx.lineTo(x,y):ctx.moveTo(x,y);
    });
    ctx.strokeStyle="#10b981";
    ctx.lineWidth = 2.3;
    ctx.shadowColor = "#10b98144";
    ctx.shadowBlur = 1.7;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Draw "HEAVY USER" text if heavy
    if(isHeavy) {
        ctx.save();
        ctx.font = "bold 13px Segoe UI";
        ctx.fillStyle = "#dc2626";
        ctx.textAlign = "left";
        ctx.textBaseline = "top";
        ctx.shadowColor = "#fff";
        ctx.shadowBlur = 0.5;
        ctx.fillText("HEAVY USER", 8, 6);
        ctx.restore();
    }
}

// --- COLOR FOR BADGE ---
function getColor(val, avg){
    if(val>avg*1.5) return "#dc2626";
    if(val>avg) return "#f59e0b";
    return "#16a34a";
}

// --- SUMMARY + GAUGE ---
// SWAPPED: Upload = total rx, Download = total tx
function updateSummary(){
    let rx=0,tx=0,net=0,top=null;
    allData.forEach(u=>{
        let t=(+u.rx_mbps||0)+(+u.tx_mbps||0);
        rx+=+u.rx_mbps||0;
        tx+=+u.tx_mbps||0;
        net+=t;
        if(!top||t>top.t) top={name:u.user,t};
    });
    // Upload is Rx, Download is Tx
    animateValue(totalRxEl,parseFloat(totalRxEl.innerText)||0,rx);
    animateValue(totalTxEl,parseFloat(totalTxEl.innerText)||0,tx);
    animateValue(totalNetEl,parseFloat(totalNetEl.innerText)||0,net);
    activeUsers.innerText=allData.length;
    topUserEl.innerText=top?top.name:"-";
    // update gauges
    drawGauge(document.getElementById('gauge-rx'), rx, maxRx, "#3b82f6");
    drawGauge(document.getElementById('gauge-tx'), tx, maxTx, "#10b981");
    drawGauge(document.getElementById('gauge-net'), net, maxNet, "#8b5cf6");
}

// --- RENDER USERS ---
// SWAPPED: Upload = rx, Download = tx
function render(filtered){
    let search=document.getElementById('search').value.trim();
    if(!search){
        users.innerHTML="🔍 Start typing to search users...";
        return;
    }
    if(!filtered.length){
        users.innerHTML="No users found";
        return;
    }
    let avg=filtered.reduce((s,u)=>s+(+u.rx_mbps + +u.tx_mbps),0)/filtered.length;
    filtered.sort((a,b)=>(b.rx_mbps+b.tx_mbps)-(a.rx_mbps+a.tx_mbps));
    let html='';
    heavyMap = {};
    filtered.forEach(u=>{
        let rx=+u.rx_mbps||0;
        let tx=+u.tx_mbps||0;
        let total=rx+tx;
        if(!history[u.user]) history[u.user]={rx:[], tx:[]};
        history[u.user].rx.push(rx);
        history[u.user].tx.push(tx);
        if(history[u.user].rx.length>20) history[u.user].rx.shift();
        if(history[u.user].tx.length>20) history[u.user].tx.shift();
        let heavy=total>avg*1.5;
        if(heavy) heavyMap[u.user] = true;
        let color=getColor(total,avg);

        html+=`
        <div class="card ${heavy?'heavy':''}">
            <div class="card-header">
                <span class="username">${u.user}</span>
                ${u.ip ? `<span class="ip" title="IP">${u.ip}</span>` : ''}
                <span class="speed-badge" style="background:${color}" title="Total bandwidth: ${total.toFixed(2)} Mbps">
                    ${total.toFixed(2)} Mbps
                </span>
            </div>
            <div class="speed-row">
                <span class="speed-number upload"><span class="speed-icon">⬆</span>${rx.toFixed(2)}</span>
                <span class="stat-label">Mbps Upload</span>
            </div>
            <div class="speed-row">
                <span class="speed-number download"><span class="speed-icon">⬇</span>${tx.toFixed(2)}</span>
                <span class="stat-label">Mbps Download</span>
            </div>
            <canvas class="user-graph-canvas" id="g-${u.user}"></canvas>
            <div class="legend">
                <span class="ul"></span>Upload
                <span class="dl"></span>Download
            </div>
        </div>`;
    });
    users.innerHTML=html;
    filtered.forEach(u=>{
        let c=document.getElementById(`g-${u.user}`);
        if(c) drawGraph(c,history[u.user].rx, history[u.user].tx, !!heavyMap[u.user]);
    });
}

// --- LOAD DATA ---
function loadData(){
    fetch('pppoe.php')
    .then(r=>r.json())
    .then(d=>{
        allData=d;
        // Optionally update gauge scaling based on observed peaks
        let rx = allData.reduce((s,u)=>s+ +u.rx_mbps,0);
        let tx = allData.reduce((s,u)=>s+ +u.tx_mbps,0);
        let net = allData.reduce((s,u)=>s+ (+u.rx_mbps)+(+u.tx_mbps),0);
        maxRx = Math.max(maxRx, rx*1.3, 30);
        maxTx = Math.max(maxTx, tx*1.3, 30);
        maxNet = Math.max(maxNet, net*1.3, 60);
        updateSummary();
        applyFilter();
    });
}

function applyFilter(){
    let search=document.getElementById('search').value.toLowerCase();
    let filtered=allData.filter(u=>u.user.toLowerCase().includes(search));
    render(filtered);
}

function startInterval(){
    if(timer) clearInterval(timer);
    timer=setInterval(loadData,document.getElementById('interval').value);
}

const users=document.getElementById('users');
const totalRxEl=document.getElementById('totalRx');
const totalTxEl=document.getElementById('totalTx');
const totalNetEl=document.getElementById('totalNet');
const activeUsers=document.getElementById('activeUsers');
const topUserEl=document.getElementById('topUser');

document.getElementById('search').addEventListener('input',applyFilter);
document.getElementById('interval').addEventListener('change',startInterval);

startInterval();
loadData();
</script>

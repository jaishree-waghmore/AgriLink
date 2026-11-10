const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const inr = n => "₹" + Number(n).toLocaleString("en-IN");
const ICON = {tomato:"🍅",mango:"🥭",potato:"🥔",banana:"🍌",milk:"🥛",chilli:"🌶️",wheat:"🌾",onion:"🧅",chicken:"🍗"};
const icon = c => ICON[String(c).toLowerCase()] || "🌱";
const api = async (u, o) => { const r = await fetch(u, o); const d = await r.json(); if (!r.ok) throw new Error(d.error || "Error"); return d; };
const post = (u, b) => api(u, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(b)});
function toast(m){ const t=$("#toast"); t.textContent=m; t.classList.add("show"); setTimeout(()=>t.classList.remove("show"),2800); }
let META = {}, charts = {}, map, layer;

/* ---------- tabs ---------- */
document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => show(b.dataset.tab));
function show(t){
  document.querySelectorAll(".tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab === t));
  document.querySelectorAll(".tab").forEach(s => s.classList.toggle("active", s.id === "tab-" + t));
  if (t === "dashboard") loadDash();
  if (t === "market") loadMarket();
  if (t === "processors") loadDemands();
  if (t === "map") loadMap();
}
function refresh(){ const a = document.querySelector(".tabs button.active").dataset.tab; show(a); }

/* ---------- dashboard ---------- */
function count(el, to){
  const pre = el.dataset.prefix || "", suf = el.dataset.suffix || "", t0 = performance.now();
  (function step(t){ const p = Math.min((t - t0) / 900, 1); el.textContent = pre + Math.round(to * p).toLocaleString("en-IN") + suf; if (p < 1) requestAnimationFrame(step); })(t0);
}
function chart(id, cfg){ if (charts[id]) charts[id].destroy(); charts[id] = new Chart($("#" + id), cfg); }
async function loadDash(){
  const s = await api("/api/stats");
  count($("#s_kg"), s.listed_kg); count($("#s_urgent"), s.urgent_lots);
  count($("#s_rescued"), s.rescued_kg); count($("#s_income"), s.extra_income);
  const crops = Object.keys(s.by_crop), pal = ["#2e7d32","#f9a825","#d32f2f","#1976d2","#8e24aa","#00897b","#ef6c00","#6d4c41","#5e35b1"];
  chart("chartCrop", {type:"doughnut", data:{labels:crops, datasets:[{data:crops.map(c => s.by_crop[c]), backgroundColor:pal}]}});
  const vc = Object.keys(s.value);
  chart("chartValue", {type:"bar", data:{labels:vc, datasets:[
    {label:"Sold raw", data:vc.map(c => s.value[c][0]), backgroundColor:"#bdbdbd"},
    {label:"After processing", data:vc.map(c => s.value[c][1]), backgroundColor:"#2e7d32"}]}});
  $("#feed").innerHTML = s.feed.length ? s.feed.map(f => `<li>✅ ${esc(f.text)} (${f.kg} kg)</li>`).join("")
    : "<li>No deals yet. Go to Marketplace and match an urgent lot with a processor!</li>";
}

/* ---------- marketplace ---------- */
function lotCard(p){
  const cls = p.days_left <= 3 ? "red" : p.days_left <= 5 ? "orange" : "green";
  const label = p.days_left < 0 ? "Expired" : `${p.days_left} day${p.days_left === 1 ? "" : "s"} left` + (p.days_left <= 3 ? " · URGENT" : "");
  const pct = Math.max(0, Math.min(100, p.shelf_pct));
  const ok = p.status === "available";
  return `<div class="card ${ok ? "" : "matched"}">
    <div class="row"><span class="badge ${cls}">${label}</span><span class="chip">${esc(p.category)}</span></div>
    <h3>${icon(p.crop)} ${esc(p.crop)}</h3>
    <div class="bar"><i style="width:${pct}%;background:${cls === "red" ? "#d32f2f" : cls === "orange" ? "#f57c00" : "#388e3c"}"></i></div>
    <p><b>${esc(p.farmer)}</b> · ${esc(p.district)}</p>
    <p>${p.quantity_kg} kg at <b>${inr(p.price_per_kg)}/kg</b> = ${inr(p.quantity_kg * p.price_per_kg)}</p>
    <p class="verdict">${p.verdict ? `${p.verdict} (market ~${inr(p.ref_price)}/kg)` : ""}</p>
    <p>📞 ${esc(p.contact || "N/A")}</p>
    ${ok ? `<div class="btns"><button onclick="openMatch(${p.id})">🤝 Find processors</button><button class="alt" onclick="openIdeas(${p.id})">💡 Ideas</button></div>`
         : `<p><b>✅ Matched with a processor</b></p>`}
  </div>`;
}
async function loadMarket(){
  const p = new URLSearchParams({q:$("#q").value, district:$("#fDistrict").value, category:$("#fCategory").value, sort:$("#fSort").value, urgent:$("#fUrgent").checked ? "1" : "0"});
  const d = await api("/api/produce?" + p);
  $("#cards").innerHTML = d.length ? d.map(lotCard).join("") : "<p>No produce found.</p>";
}
["q","fDistrict","fCategory","fSort","fUrgent"].forEach(id => $("#" + id).addEventListener(id === "q" ? "input" : "change", loadMarket));

/* ---------- modals: smart match + ideas ---------- */
const modal = $("#modal"); $("#mClose").onclick = () => modal.classList.add("hidden");
async function openMatch(id){
  const d = await api("/api/match/" + id), l = d.lot;
  let h = `<h2>${icon(l.crop)} Smart match: ${esc(l.crop)}</h2><p>${l.quantity_kg} kg · ${esc(l.district)} · ${l.days_left} days left</p>`;
  if (!d.matches.length) h += "<p style='margin-top:12px'>No processor demand for this crop yet. Try the Ideas button.</p>";
  d.matches.forEach(m => h += `<div class="match">
      <div class="row"><b>${esc(m.processor)}</b><span class="score">${m.score}% match</span></div>
      <p>📍 ${esc(m.district)} (${m.distance_km} km) · wants ${m.quantity_kg} kg (covers ${m.coverage}%)</p>
      <p>Offer <b>${inr(m.offer_price)}/kg</b> vs your ${inr(l.price_per_kg)}/kg · <span class="gain">${m.farmer_gain >= 0 ? "+" : ""}${inr(m.farmer_gain)} for you</span></p>
      <div class="btns"><button onclick="accept(${l.id},${m.id})">Accept deal</button></div></div>`);
  $("#mBody").innerHTML = h; modal.classList.remove("hidden");
}
async function accept(pid, did){
  try { await post("/api/deal", {produce_id:pid, demand_id:did}); modal.classList.add("hidden"); toast("🎉 Deal confirmed! Food rescued."); refresh(); }
  catch(e){ toast(e.message); }
}
async function openIdeas(id){
  const d = await api("/api/suggest/" + id);
  $("#mBody").innerHTML = `<h2>${icon(d.crop)} ${esc(d.crop)}: value-add ideas</h2><p>Selling raw: <b>${inr(d.raw_value)}</b></p>
    <ul class="ideas">${d.ideas.map(i => `<li>${esc(i.product)}: ~${inr(i.value)} <b class="gain">(+${inr(i.gain)})</b></li>`).join("")}</ul>
    <small>Indicative estimates using assumed value-add multipliers.</small>`;
  modal.classList.remove("hidden");
}

/* ---------- processors ---------- */
async function loadDemands(){
  const d = await api("/api/demands");
  $("#demands").innerHTML = d.map(x => `<div class="card"><div class="row"><b>🏭 ${esc(x.processor)}</b><span class="badge blue">${esc(x.crop)}</span></div>
    <p>Needs <b>${x.quantity_kg} kg</b> at <b>${inr(x.offer_price)}/kg</b></p><p>📍 ${esc(x.district)} · Makes: ${esc(x.product || "-")}</p><p>📞 ${esc(x.contact || "N/A")}</p></div>`).join("");
}
$("#dBtn").onclick = async () => {
  try {
    await post("/api/demands", {processor:$("#d_processor").value, crop:$("#d_crop").value, quantity_kg:$("#d_qty").value, offer_price:$("#d_offer").value, district:$("#d_district").value, product:$("#d_product").value, contact:$("#d_contact").value});
    ["d_processor","d_crop","d_qty","d_offer","d_product","d_contact"].forEach(i => $("#" + i).value = ""); toast("Demand posted!"); loadDemands();
  } catch(e){ $("#dMsg").textContent = e.message; }
};

/* ---------- map ---------- */
async function loadMap(){
  if (!map){ map = L.map("map").setView([14.6, 76.2], 7); L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {attribution:"© OpenStreetMap"}).addTo(map); layer = L.layerGroup().addTo(map); }
  setTimeout(() => map.invalidateSize(), 100); layer.clearLayers();
  const [lots, dem] = await Promise.all([api("/api/produce"), api("/api/demands")]);
  lots.filter(l => l.lat && l.status === "available").forEach(l => {
    const c = l.days_left <= 3 ? "#d32f2f" : l.days_left <= 5 ? "#f57c00" : "#388e3c";
    L.circleMarker([l.lat + (l.id % 5 - 2) * .03, l.lng + (l.id % 3 - 1) * .03], {radius:10, color:c, fillColor:c, fillOpacity:.8})
      .bindPopup(`<b>${icon(l.crop)} ${esc(l.crop)}</b><br>${esc(l.farmer)}, ${esc(l.district)}<br>${l.quantity_kg} kg · ${l.days_left} days left<br><a href="#" onclick="openMatch(${l.id});return false">Find processors</a>`).addTo(layer);
  });
  dem.forEach(d => { const ll = META.districts[d.district]; if (ll) L.marker([ll[0] - .04, ll[1] + .04], {icon:L.divIcon({html:"🏭", className:"", iconSize:[24,24]})}).bindPopup(`<b>${esc(d.processor)}</b><br>Needs ${d.quantity_kg} kg ${esc(d.crop)} at ${inr(d.offer_price)}/kg`).addTo(layer); });
}

/* ---------- add produce ---------- */
$("#f_crop").addEventListener("input", e => {
  const k = e.target.value.trim().toLowerCase();
  if (META.shelf[k]) $("#f_shelf").value = META.shelf[k];
  $("#hint").textContent = META.ref_price[k] ? `💡 Typical market price ~${inr(META.ref_price[k])}/kg · shelf life ~${META.shelf[k]} days` : "";
});
$("#fBtn").onclick = async () => {
  try {
    await post("/api/produce", {farmer:$("#f_farmer").value, category:$("#f_category").value, crop:$("#f_crop").value, quantity_kg:$("#f_qty").value, price_per_kg:$("#f_price").value, district:$("#f_district").value, harvest_date:$("#f_harvest").value, shelf_life_days:$("#f_shelf").value, contact:$("#f_contact").value});
    ["f_farmer","f_crop","f_qty","f_price","f_shelf","f_contact"].forEach(i => $("#" + i).value = "");
    $("#fMsg").textContent = ""; toast("✅ Produce listed!"); show("market");
  } catch(e){ $("#fMsg").textContent = e.message; }
};

/* ---------- init ---------- */
(async () => {
  META = await api("/api/meta");
  const opts = Object.keys(META.districts).sort().map(d => `<option>${d}</option>`).join("");
  $("#fDistrict").innerHTML += opts; $("#f_district").innerHTML = opts; $("#d_district").innerHTML = opts;
  $("#cropList").innerHTML = Object.keys(META.shelf).map(c => `<option value="${c[0].toUpperCase() + c.slice(1)}">`).join("");
  $("#f_harvest").value = new Date().toISOString().slice(0, 10);
  loadDash();
})();

# app.py
import os, json, requests, streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Localisation Google", page_icon="📍")
st.title("📍 Ma position + adresse (Google)")

GMAPS_KEY = st.secrets.get("GMAPS_API_KEY") or os.getenv("GMAPS_API_KEY")

val = components.html("""
<div style="display:flex;gap:8px;align-items:center">
  <button id="btn" style="padding:8px 12px;border-radius:6px;cursor:pointer">📍 Localiser</button>
  <span id="info"></span>
</div>
<script>
function send(v){window.parent.postMessage({isStreamlitMessage:true,type:"streamlit:setComponentValue",value:v},"*");}
function locate(){
  const info=document.getElementById("info");
  if(!navigator.geolocation){info.textContent="Géoloc non supportée."; send(null); return;}
  navigator.geolocation.getCurrentPosition(
    p=>{const out={lat:p.coords.latitude,lon:p.coords.longitude,acc:p.coords.accuracy};
        info.textContent=`OK (±${Math.round(out.acc)} m)`; send(JSON.stringify(out));},
    e=>{info.textContent=(e.code===1)?"Permission refusée":"Position indisponible"; send(null);},
    {enableHighAccuracy:true,timeout:15000,maximumAge:0});
}
document.getElementById("btn").onclick=locate;
</script>
""", height=50)

def gmaps_reverse(lat: float, lon: float, key: str):
    if not key:
        return None, "Manque GMAPS_API_KEY"
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    r = requests.get(url, params={"latlng": f"{lat},{lon}", "key": key, "language": "fr"}, timeout=10)
    if not r.ok:
        return None, f"HTTP {r.status_code}: {r.text[:200]}"
    data = r.json()
    if data.get("status") != "OK" or not data.get("results"):
        return None, f"Status: {data.get('status')}"
    addr = data["results"][0]["formatted_address"]
    return {"adresse": addr, "lat": lat, "lon": lon}, None

if val:
    try:
        d = json.loads(val)
        lat, lon = d["lat"], d["lon"]
        st.write(f"**Lat:** {lat:.6f}  |  **Lon:** {lon:.6f}  |  **Précision:** ±{int(d.get('acc',0))} m")
        res, err = gmaps_reverse(lat, lon, GMAPS_KEY)
        if res:
            st.success(res["adresse"])
            st.code(f"Latitude: {lat:.6f}\nLongitude: {lon:.6f}", language="text")
            st.link_button("Ouvrir dans Google Maps", f"https://www.google.com/maps?q={lat},{lon}")
        else:
            st.error("Reverse geocoding KO")
            st.caption(err or "")
    except Exception as e:
        st.error("Données navigateur illisibles.")
        st.caption(str(e))
else:
    st.info("Clique sur « Localiser » et autorise la géolocalisation.")

st.caption("Met ta clé dans st.secrets['GMAPS_API_KEY'] ou variable d'environnement GMAPS_API_KEY. HTTPS requis.")

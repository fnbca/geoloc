# app.py
import json, math, requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Géolocalisation + Adresse", page_icon="📍")
st.title("📍 Localiser & afficher l'adresse")

# ====== 1) FRONT (JS) : récupère la position (auto + bouton Réessayer)
val = components.html("""
<div style="display:flex;gap:8px;align-items:center">
  <button id="retry" style="padding:8px 12px;border-radius:6px;cursor:pointer">📍 Réessayer</button>
  <span id="info">Recherche de localisation…</span>
</div>
<script>
function send(v){ window.parent.postMessage(
  {isStreamlitMessage:true,type:"streamlit:setComponentValue",value:v},"*"); }
function locate(){
  const el = document.getElementById("info");
  if(!navigator.geolocation){ el.textContent="Géolocalisation non supportée."; send(JSON.stringify({error:"no_geolocation"})); return; }
  navigator.geolocation.getCurrentPosition(
    p => { const out={lat:p.coords.latitude, lon:p.coords.longitude, accuracy:p.coords.accuracy};
           el.textContent=`✅ OK (±${Math.round(out.accuracy)} m)`; send(JSON.stringify(out)); },
    e => { el.textContent=(e.code===1)?"Permission refusée.":(e.code===2)?"Position indisponible.":"Erreur.";
           // Fallback visible : Paris
           send(JSON.stringify({lat:48.8566, lon:2.3522, accuracy:999, note:"fallback"})); },
    {enableHighAccuracy:true, timeout:15000, maximumAge:0}
  );
}
document.getElementById("retry").onclick = locate;
locate();
</script>
""", height=50)

# ====== 2) BACK : reverse IGN WFS (BAN) avec buffer + diagnostic
def reverse_ign(lat, lon, meters=80, layers=("BAN.DATA.GOUV:ban", "BAN:adresse")):
    dlat = meters / 111_320.0
    dlon = meters / (111_320.0 * math.cos(math.radians(lat)))
    ring = []
    for i in range(32):
        ang = 2*math.pi*i/32
        ring.append([lon + dlon*math.cos(ang), lat + dlat*math.sin(ang)])
    ring.append(ring[0])
    geom = {"type":"Polygon","coordinates":[ring]}

    last_diag = {}
    for layer in layers:
        try:
            r = requests.get(
                "https://apicarto.ign.fr/api/wfs/geoportail",
                params={"source": layer, "geom": json.dumps(geom), "_limit":"60"},
                headers={"User-Agent":"Streamlit-Geo/1.0"},
                timeout=12,
            )
            last_diag = {"layer": layer, "http": r.status_code}
            if not r.ok:
                last_diag["body"] = r.text[:300]
                continue
            data = r.json()
            feats = data.get("features", [])
            last_diag["features"] = len(feats)
            if not feats:  # essaie couche suivante
                continue
            best = min(
                feats,
                key=lambda f: (f["geometry"]["coordinates"][0]-lon)**2 +
                              (f["geometry"]["coordinates"][1]-lat)**2
            )
            x, y = best["geometry"]["coordinates"]
            p = best.get("properties", {})
            label = p.get("nom_complet") or p.get("label") or p.get("numero_nom_voie") or "Adresse inconnue"
            return {"adresse": label.strip(), "lat": y, "lon": x, "layer": layer}, last_diag
        except Exception as e:
            last_diag = {"layer": layer, "error": str(e)}
            continue
    return None, last_diag

# ====== 3) Traitement & UI
if val is None:
    st.error("Aucune valeur reçue. Vérifie HTTPS et les autorisations du navigateur.")
else:
    # 'val' est une string JSON envoyée par le composant
    try:
        data = json.loads(val)
    except Exception as e:
        st.error("Réponse navigateur illisible.")
        st.code(str(val))
        st.caption(f"Parse error: {e}")
        st.stop()

    if isinstance(data, dict) and "lat" in data and "lon" in data:
        lat, lon = float(data["lat"]), float(data["lon"])
        st.subheader("📌 Coordonnées")
        st.write(f"Latitude : **{lat:.6f}**")
        st.write(f"Longitude : **{lon:.6f}**")
        if "accuracy" in data: st.write(f"Précision : ±{int(round(data['accuracy']))} m")
        if data.get("note") == "fallback":
            st.info("Localisation refusée/indispo : valeurs par défaut utilisées (Paris).")

        st.subheader("🏠 Adresse (IGN)")
        res, diag = reverse_ign(lat, lon)
        if res:
            st.success(res["adresse"])
            st.caption(f"Source : {res['layer']}")
            st.code(f"Latitude: {res['lat']:.6f}\nLongitude: {res['lon']:.6f}", language="text")
            st.text(f"Position: {res['lat']:.6f},{res['lon']:.6f} | {res['adresse']}")
        else:
            st.error("Aucune adresse trouvée ou erreur API.")
            with st.expander("Diagnostic"):
                st.json(diag)
            st.info("Essaie à l’extérieur, puis augmente le buffer (ex. 150 m).")
    else:
        st.error("Format inattendu depuis le navigateur :")
        st.code(str(data))

st.caption("⚠️ HTTPS (ou localhost) requis. Autorise la localisation pour ce site.")

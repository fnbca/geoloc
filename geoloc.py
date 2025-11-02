import json, math, requests, streamlit as st, streamlit.components.v1 as components

st.set_page_config(page_title="Localisation robuste", page_icon="📍")
st.title("📍 Localisation + Adresse (avec diagnostic)")

# === 1) FRONT : récup auto + bouton retry
val = components.html("""
<div style="display:flex;gap:8px;align-items:center">
  <button id="retry" style="padding:8px 12px;border-radius:6px;cursor:pointer">🔄 Réessayer</button>
  <span id="info">Recherche de localisation…</span>
</div>
<script>
function send(v){
  window.parent.postMessage({isStreamlitMessage:true,type:"streamlit:setComponentValue",value:v},"*");
}
function locate(){
  const el = document.getElementById("info");
  if(!navigator.geolocation){ el.textContent="Géolocalisation non supportée."; send(JSON.stringify({error:"no_geolocation"})); return; }
  navigator.geolocation.getCurrentPosition(
    pos=>{
      const out={lat:pos.coords.latitude,lon:pos.coords.longitude,accuracy:pos.coords.accuracy};
      el.textContent=`✅ OK (±${Math.round(out.accuracy)} m)`;
      send(JSON.stringify(out));
    },
    err=>{
      el.textContent = (err.code===1)?"Permission refusée.":
                       (err.code===2)?"Position indisponible.":"Erreur de géolocalisation.";
      // fallback visible (Paris)
      send(JSON.stringify({lat:48.8566,lon:2.3522,accuracy:999, note:"fallback"}));
    },
    {enableHighAccuracy:true,timeout:15000,maximumAge:0}
  );
}
document.getElementById("retry").onclick = locate;
locate();
</script>
""", height=50)

# === 2) BACK : reverse IGN avec 2 couches + diagnostics
def ign_reverse(lat, lon, meters=80, layers=("BAN.DATA.GOUV:ban","BAN:adresse")):
    dlat = meters / 111_320.0
    dlon = meters / (111_320.0 * math.cos(math.radians(lat)))
    ring=[]
    for i in range(32):
        ang = 2*math.pi*i/32
        ring.append([lon + dlon*math.cos(ang), lat + dlat*math.sin(ang)])
    ring.append(ring[0])
    geom = {"type":"Polygon","coordinates":[ring]}

    last = {}
    for layer in layers:
        try:
            r = requests.get(
                "https://apicarto.ign.fr/api/wfs/geoportail",
                params={"source": layer, "geom": json.dumps(geom), "_limit":"60"},
                headers={"User-Agent":"Streamlit-Geo/1.0"},
                timeout=12,
            )
            last = {"layer": layer, "http": r.status_code}
            if not r.ok:
                last["body"] = r.text[:400]
                continue
            data = r.json()
            last["json_keys"] = list(data.keys())
            feats = data.get("features", [])
            last["features"] = len(feats)
            if not feats:
                continue
            best = min(feats, key=lambda f:(f["geometry"]["coordinates"][0]-lon)**2 + (f["geometry"]["coordinates"][1]-lat)**2)
            x, y = best["geometry"]["coordinates"]
            p = best.get("properties", {})
            label = p.get("nom_complet") or p.get("label") or p.get("numero_nom_voie") or "Adresse inconnue"
            return {"adresse": label.strip(), "lat": y, "lon": x, "layer": layer}, last
        except Exception as e:
            last = {"layer": layer, "error": str(e)}
            continue
    return None, last

# === 3) Traitement + affichage (avec garde-fous)
if val is None:
    st.warning("Aucune valeur reçue du composant. Vérifie HTTPS / autorisations.")
else:
    try:
        # 'val' peut être str JSON ou déjà dict; on gère les 2
        data = json.loads(val) if isinstance(val, str) else val
    except Exception as e:
        st.error("Impossible de décoder la valeur reçue du navigateur.")
        st.code(str(val))
        st.caption(f"Parse error: {e}")
        st.stop()

    # Affichage coords brutes
    if isinstance(data, dict) and ("lat" in data and "lon" in data):
        lat, lon = float(data["lat"]), float(data["lon"])
        st.subheader("📌 Coordonnées")
        st.write(f"Latitude : **{lat:.6f}**")
        st.write(f"Longitude : **{lon:.6f}**")
        if "accuracy" in data: st.write(f"Précision (navigateur) : ±{int(round(data['accuracy']))} m")
        if data.get("note") == "fallback":
            st.info("Localisation refusée/indispo : valeurs par défaut utilisées (Paris).")

        # Reverse
        res, diag = ign_reverse(lat, lon)
        st.subheader("🏠 Adresse (IGN)")
        if res:
            st.success(f"{res['adresse']}")
            st.caption(f"Source: {res['layer']}")
        else:
            st.error("Aucune adresse trouvée ou erreur API.")
            st.write("Diagnostic :")
            st.json(diag)
    else:
        st.error("Format de données inattendu depuis le navigateur :")
        st.code(str(data))

st.caption("Rappels : HTTPS (ou localhost) obligatoire, autoriser la localisation dans le navigateur.")

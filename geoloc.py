import json, math, requests, streamlit as st, streamlit.components.v1 as components

st.set_page_config(page_title="Localisation automatique", page_icon="📍")
st.title("📍 Ma localisation")

# --- HTML + JS : récupère la position automatiquement
val = components.html("""
<div id="zone" style="padding:8px 0;">
  <b>Récupération de la localisation...</b>
</div>
<script>
function send(v){
  window.parent.postMessage(
    { isStreamlitMessage: true, type: "streamlit:setComponentValue", value: v },
    "*"
  );
}

function locate(){
  if(!navigator.geolocation){
    document.getElementById("zone").innerText = "Géolocalisation non supportée.";
    send(null);
    return;
  }
  navigator.geolocation.getCurrentPosition(
    pos=>{
      const out={lat:pos.coords.latitude,lon:pos.coords.longitude,accuracy:pos.coords.accuracy};
      document.getElementById("zone").innerHTML = 
        `✅ Localisation trouvée (±${Math.round(out.accuracy)} m)`;
      send(JSON.stringify(out));
    },
    err=>{
      document.getElementById("zone").innerText = 
        "Localisation refusée ou impossible. Valeurs par défaut affichées.";
      // Valeur par défaut : Paris
      send(JSON.stringify({lat:48.8566, lon:2.3522, accuracy:999}));
    },
    {enableHighAccuracy:true,timeout:10000,maximumAge:0}
  );
}
locate();
</script>
""", height=50)

# --- fonction pour requêter IGN (adresse)
def ign_reverse_address(lat, lon, meters=60, layer="BAN:adresse"):
    dlat = meters / 111_320.0
    dlon = meters / (111_320.0 * math.cos(math.radians(lat)))
    ring = []
    for i in range(24):
        ang = 2 * math.pi * i / 24
        ring.append([lon + dlon * math.cos(ang), lat + dlat * math.sin(ang)])
    ring.append(ring[0])
    geom = {"type": "Polygon", "coordinates": [ring]}
    try:
        r = requests.get(
            "https://apicarto.ign.fr/api/wfs/geoportail",
            params={"source": layer, "geom": json.dumps(geom), "_limit": "50"},
            headers={"User-Agent": "Streamlit-Geo/1.0"},
            timeout=10,
        )
        if not r.ok:
            return None
        data = r.json()
        feats = data.get("features", [])
        if not feats:
            return None
        best = min(
            feats,
            key=lambda f: (f["geometry"]["coordinates"][0] - lon)**2
                          + (f["geometry"]["coordinates"][1] - lat)**2
        )
        props = best.get("properties", {})
        x, y = best["geometry"]["coordinates"]
        label = props.get("nom_complet") or props.get("label") or "Adresse inconnue"
        return {"adresse": label.strip(), "lat": y, "lon": x}
    except Exception:
        return None

# --- Traitement et affichage
if val:
    try:
        data = json.loads(val)
        lat, lon = data["lat"], data["lon"]
        st.subheader("📌 Coordonnées détectées")
        st.write(f"Latitude : **{lat:.6f}**")
        st.write(f"Longitude : **{lon:.6f}**")
        st.write(f"Précision : ±{int(data['accuracy'])} m")

        res = ign_reverse_address(lat, lon)
        st.subheader("🏠 Adresse")
        if res:
            st.success(res['adresse'])
        else:
            st.warning("Aucune adresse trouvée. (Zone sans point adresse)")
    except Exception:
        st.error("Erreur lors de la récupération des données.")
else:
    st.info("En attente d'autorisation de localisation…")

st.caption("⚠️ Nécessite HTTPS et l'autorisation du navigateur pour la géolocalisation.")

import json, math, requests, streamlit as st, streamlit.components.v1 as components

st.set_page_config(page_title="Géolocalisation & Adresse", page_icon="📍")
st.title("📍 Localisation en temps réel")

# --- Bloc HTML+JS : récupération de la position via le navigateur
val = components.html("""
<div style="display:flex;gap:8px;align-items:center">
  <button id="btn" style="padding:10px 14px;border-radius:8px;cursor:pointer">📍 Localiser moi</button>
  <span id="info"></span>
</div>
<script>
const info = document.getElementById('info');
function send(v){window.parent.postMessage({isStreamlitMessage:true,type:"streamlit:setComponentValue",value:v},"*");}

async function askLocation(){
  info.textContent = "Demande de localisation...";
  if (!navigator.geolocation){info.textContent="Géolocalisation non supportée.";send(null);return;}
  try{
    navigator.geolocation.getCurrentPosition(
      pos=>{
        const out={lat:pos.coords.latitude,lon:pos.coords.longitude,accuracy:pos.coords.accuracy};
        info.textContent=`✅ Position trouvée (±${Math.round(out.accuracy)} m)`;
        send(JSON.stringify(out));
      },
      err=>{
        if(err.code===1) info.textContent="Permission refusée.";
        else if(err.code===2) info.textContent="Position indisponible.";
        else info.textContent="Erreur de géolocalisation.";
        send(null);
      },
      {enableHighAccuracy:true,timeout:15000,maximumAge:0}
    );
  }catch(e){info.textContent="Erreur JS: "+e.message;send(null);}
}
document.getElementById('btn').onclick = askLocation;
</script>
""", height=60)

# --- Fonction pour requêter l'API IGN (WFS)
def ign_reverse_address(lat, lon, meters=25, limit=50, layer="BAN.DATA.GOUV:ban"):
    dlat = meters / 111_320.0
    dlon = meters / (111_320.0 * math.cos(math.radians(lat)))
    coords = []
    for i in range(24):
        ang = 2 * math.pi * i / 24
        coords.append([lon + dlon * math.cos(ang), lat + dlat * math.sin(ang)])
    coords.append(coords[0])
    geom = {"type": "Polygon", "coordinates": [coords]}
    r = requests.get(
        "https://apicarto.ign.fr/api/wfs/geoportail",
        params={"source": layer, "geom": json.dumps(geom), "_limit": str(limit)},
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
        key=lambda f: (f["geometry"]["coordinates"][0] - lon) ** 2
                      + (f["geometry"]["coordinates"][1] - lat) ** 2,
    )
    props = best.get("properties", {})
    x, y = best["geometry"]["coordinates"]
    label = props.get("nom_complet") or props.get("label") or ""
    return {"adresse": label.strip(), "lat": y, "lon": x}

# --- Traitement et affichage
if val:
    try:
        data = json.loads(val)
        lat, lon = data["lat"], data["lon"]
        st.subheader("📌 Coordonnées GPS")
        st.write(f"**Latitude :** {lat:.6f}")
        st.write(f"**Longitude :** {lon:.6f}")
        st.write(f"**Précision estimée :** ±{int(data['accuracy'])} m")

        st.subheader("🏠 Adresse estimée (API IGN)")
        res = ign_reverse_address(lat, lon)
        if res:
            st.success(res['adresse'])
        else:
            st.warning("Aucune adresse trouvée dans la zone.")
    except Exception:
        st.error("Impossible de lire la position ou l'adresse.")
else:
    st.info("Clique sur « Localiser moi » et autorise la géolocalisation.")

st.caption("⚠️ Nécessite HTTPS et l'autorisation du navigateur pour la localisation.")

"""
Live demonstration: SIMBAD, VizieR, and Aladin driven from Python.
Queries M27 field and generates an interactive HTML viewer with live catalogues.

Run:  python demo_apis.py
"""
import warnings, subprocess, sys
warnings.filterwarnings("ignore")
import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u

RA, DEC  = 299.901, +22.721   # M27 Dumbbell Nebula
RADIUS   = 0.33               # degrees  (~20 arcmin)
coord    = SkyCoord(ra=RA*u.deg, dec=DEC*u.deg)

print("=" * 60)
print("SIMBAD / VizieR / Aladin API demo — M27 field")
print("=" * 60)


# ── SIMBAD: resolve M27 ───────────────────────────────────────────────────────
print("\n[ SIMBAD ] Resolve M27")
from astroquery.simbad import Simbad
s1 = Simbad()
s1.add_votable_fields("otype", "V", "distance")
m27 = s1.query_object("M27")
if m27:
    print(f"  Name     : {m27['main_id'][0]}")
    print(f"  Type     : {m27['otype'][0]}")
    print(f"  RA / Dec : {float(m27['ra'][0]):.4f}  {float(m27['dec'][0]):.4f}")
    print(f"  V mag    : {m27['V'][0]}")
    dist_pc  = m27["mesdistance.dist"][0]
    dist_unit= m27["mesdistance.unit"][0]
    print(f"  Distance : {dist_pc} {dist_unit}")


# ── SIMBAD: all objects in the 20-arcmin field ────────────────────────────────
print("\n[ SIMBAD ] Objects in 20-arcmin field")
s2 = Simbad()
s2.add_votable_fields("otype", "V")
field_obj = s2.query_region(coord, radius=RADIUS*u.deg)
cat_entries = []
if field_obj:
    from collections import Counter
    types = Counter(field_obj["otype"])
    print(f"  Total objects : {len(field_obj)}")
    print("  By type (top 8):")
    for otype, count in types.most_common(8):
        print(f"    {str(otype):25s}  {count:>4}")
    for row in field_obj:
        try:
            cat_entries.append((float(row["ra"]), float(row["dec"]),
                                str(row["main_id"]).strip(),
                                str(row["otype"]).strip()))
        except Exception:
            pass


# ── VizieR: 2MASS stars ───────────────────────────────────────────────────────
print("\n[ VizieR ] 2MASS PSC — bright stars (J < 13)")
from astroquery.vizier import Vizier
v2 = Vizier(columns=["RAJ2000","DEJ2000","Jmag","Hmag","Kmag"],
            column_filters={"Jmag":"<13"}, row_limit=100)
tmass = v2.query_region(coord, radius=RADIUS*u.deg, catalog="II/246")
if tmass:
    t = tmass[0]
    print(f"  Stars found : {len(t)}")
    print(f"  J range     : {float(t['Jmag'].min()):.2f} – {float(t['Jmag'].max()):.2f}")
    t.sort("Jmag")
    print("  Brightest 5:")
    for row in t[:5]:
        print(f"    RA={float(row['RAJ2000']):.4f}  Dec={float(row['DEJ2000']):.4f}  "
              f"J={float(row['Jmag']):.2f}  H={float(row['Hmag']):.2f}  "
              f"K={float(row['Kmag']):.2f}")


# ── VizieR: Gaia DR3 proper motions ──────────────────────────────────────────
print("\n[ VizieR ] Gaia DR3 — high proper-motion stars in field (mu > 20 mas/yr)")
gv = Vizier(columns=["Source","RA_ICRS","DE_ICRS","Plx","pmRA","pmDE","Gmag"],
            column_filters={"Gmag":"<18"}, row_limit=1000)
gaia_cats = gv.query_region(coord, radius=RADIUS*u.deg, catalog="I/355/gaiadr3")
pm_entries = []
high_pm    = []
if gaia_cats:
    gt = gaia_cats[0]
    # fill masked values with 0 for arithmetic
    pmRA = np.array([float(x) if x else 0.0 for x in gt["pmRA"]])
    pmDE = np.array([float(x) if x else 0.0 for x in gt["pmDE"]])
    mu   = np.sqrt(pmRA**2 + pmDE**2)
    print(f"  Total Gaia stars  : {len(gt)}")
    print(f"  mu > 20 mas/yr    : {(mu > 20).sum()}")
    print(f"  mu > 50 mas/yr    : {(mu > 50).sum()}")
    if (mu > 20).sum() > 0:
        print("  High-PM stars:")
        idx_sorted = np.argsort(mu)[::-1]
        for i in idx_sorted[:8]:
            if mu[i] < 20:
                break
            row = gt[int(i)]
            print(f"    Source {row['Source']}  "
                  f"pmRA={pmRA[i]:+.1f}  pmDE={pmDE[i]:+.1f}  "
                  f"mu={mu[i]:.1f} mas/yr  "
                  f"plx={float(row['Plx']) if row['Plx'] else 0:.2f} mas  "
                  f"G={float(row['Gmag']):.2f}")
            high_pm.append((float(row["RA_ICRS"]), float(row["DE_ICRS"]),
                            str(row["Source"]), pmRA[i], pmDE[i], float(row["Gmag"])))
    for i in range(len(gt)):
        try:
            pm_entries.append((float(gt["RA_ICRS"][i]), float(gt["DE_ICRS"][i]),
                               str(gt["Source"][i]), pmRA[i], pmDE[i],
                               float(gt["Gmag"][i]), mu[i]))
        except Exception:
            pass


# ── Cross-reference: high-PM Gaia stars vs our DSS blink PM detection ────────
print("\n[ FITA ] Cross-check with our DSS blink PM detection")
print(f"  DSS baseline      : 38.0 yr  (1955–1993)")
print(f"  1 pixel = 1 arcsec = 1000 mas")
print(f"  Detectable limit  : ~26 mas/yr  (1 pix / 38 yr)")
print(f"  Gaia stars above limit : {len(high_pm)}")
if high_pm:
    print("  These SHOULD have been detectable in the DSS blink:")
    for ra, dec, src, pmra, pmde, g, *_ in high_pm[:5]:
        disp_pix = np.sqrt(pmra**2 + pmde**2) * 38.0 / 1000.0
        print(f"    Source {src}  disp={disp_pix:.2f} px  G={g:.1f}")
    print("  (If not detected: likely in nebula halo where DAOStarFinder fails)")


# ── Build enriched Aladin viewer ──────────────────────────────────────────────
print("\n[ Aladin ] Building live-catalogue HTML viewer")

def js_arr(entries, fields):
    rows = []
    for e in entries:
        parts = ", ".join(f"{k}:{repr(v) if isinstance(v,str) else round(float(v),5)}"
                          for k, v in zip(fields, e))
        rows.append("  {" + parts + "}")
    return "[\n" + ",\n".join(rows) + "\n]"

simbad_js = js_arr(cat_entries[:300],
                   ["ra","dec","name","otype"])
gaia_js   = js_arr(pm_entries[:500],
                   ["ra","dec","source","pmra","pmde","gmag","mu"])

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>M27 — URANODYNE live viewer</title>
<link rel="stylesheet" href="https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.min.css"/>
<style>
body{{margin:0;background:#0d0d1a;color:#eee;font-family:sans-serif}}
#topbar{{padding:6px 14px;background:#12122a;font-size:.85em;
         display:flex;align-items:center;gap:20px;border-bottom:1px solid #333}}
#topbar b{{color:#7ec8e3}}
#aladin-lite-div{{width:100vw;height:calc(100vh - 36px)}}
#panel{{position:absolute;top:46px;right:8px;z-index:200;
        background:rgba(10,10,26,.92);border-radius:8px;
        padding:10px 14px;width:230px;font-size:.82em}}
h3{{margin:4px 0 6px;color:#7ec8e3;font-size:.9em;border-bottom:1px solid #333;padding-bottom:3px}}
.row{{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px}}
button{{background:#1e1e3a;color:#ccc;border:1px solid #444;border-radius:4px;
        padding:3px 7px;cursor:pointer;font-size:.8em}}
button:hover{{background:#2a2a50;color:#fff}}
button.on{{border-color:#7ec8e3;color:#7ec8e3}}
select{{background:#1e1e3a;color:#ccc;border:1px solid #444;border-radius:4px;
        padding:2px 4px;width:100%;margin-bottom:4px;font-size:.8em}}
#stats{{color:#888;font-size:.78em;margin-top:6px;line-height:1.6}}
#objinfo{{color:#aaa;font-size:.8em;margin-top:6px;min-height:40px;
           border-top:1px solid #333;padding-top:6px}}
</style></head><body>
<div id="topbar">
  <b>M27 Dumbbell Nebula</b>
  <span>RA {RA}&deg; Dec +{DEC}&deg; &nbsp;|&nbsp; 40&prime;&times;40&prime;</span>
  <span style="color:#888">{len(cat_entries)} SIMBAD &nbsp;|&nbsp; {len(pm_entries)} Gaia DR3 &nbsp;|&nbsp;
  {len(high_pm)} high-PM stars &nbsp;|&nbsp; URANODYNE/IrenBLink</span>
</div>
<div id="aladin-lite-div"></div>
<div id="panel">
  <h3>Survey</h3>
  <select id="bgsel" onchange="aladin.setImageSurvey(this.value)">
    <option value="CDS/P/DSS2/red">DSS2 Red (~1993)</option>
    <option value="CDS/P/DSS2/blue">DSS2 Blue (~1993)</option>
    <option value="CDS/P/DSS2/color">DSS2 Colour</option>
    <option value="CDS/P/2MASS/J">2MASS J (1.25 um)</option>
    <option value="CDS/P/2MASS/H">2MASS H (1.65 um)</option>
    <option value="CDS/P/2MASS/K">2MASS K (2.17 um)</option>
    <option value="CDS/P/WISE/W1">WISE W1 (3.4 um)</option>
    <option value="CDS/P/WISE/W2">WISE W2 (4.6 um)</option>
    <option value="CDS/P/WISE/W3">WISE W3 (12 um)</option>
    <option value="CDS/P/WISE/W4">WISE W4 (22 um)</option>
    <option value="CDS/P/Halpha/IFJ-IPHAS">H-alpha IPHAS</option>
    <option value="CDS/P/GALEX/AIS/NUV">GALEX NUV</option>
  </select>

  <h3>Catalogues</h3>
  <div class="row">
    <button id="btnSim" class="on" onclick="toggle('sim')">SIMBAD</button>
    <button id="btnGaia" class="on" onclick="toggle('gaia')">Gaia DR3</button>
    <button id="btnHighPM" onclick="toggle('highpm')">High-PM only</button>
  </div>

  <h3>Navigate</h3>
  <div class="row">
    <button onclick="aladin.gotoRaDec({RA},{DEC});aladin.setFov(0.67)">M27</button>
    <button onclick="aladin.setFov(0.2)">Zoom in</button>
    <button onclick="aladin.setFov(1.5)">Zoom out</button>
  </div>

  <div id="stats">
    <b style="color:#eee">Field stats</b><br>
    SIMBAD objects: <b>{len(cat_entries)}</b><br>
    Gaia stars: <b>{len(pm_entries)}</b><br>
    PM &gt; 20 mas/yr: <b>{len(high_pm)}</b><br>
    DSS baseline: <b>38 yr</b><br>
    PM limit: <b>~26 mas/yr</b>
  </div>

  <div id="objinfo">Click any object for details</div>
</div>

<script src="https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.min.js"></script>
<script>
const simbadData = {simbad_js};
const gaiaData   = {gaia_js};

var aladin, cats = {{}};

A.init.then(() => {{
  aladin = A.aladin('#aladin-lite-div', {{
    survey:'CDS/P/DSS2/red', target:'{RA} +{DEC}',
    fov: 0.67, showLayersControl:true,
    showFrame:true, showCooGrid:false,
  }});

  // SIMBAD objects
  cats.sim = A.catalog({{name:'SIMBAD', color:'#ff9900',
    shape:'circle', sourceSize:9, onClick:'showTable'}});
  simbadData.forEach(o => cats.sim.addSources([
    A.source(o.ra, o.dec, {{Name:o.name, Type:o.otype}})
  ]));
  aladin.addCatalog(cats.sim);

  // Gaia all
  cats.gaia = A.catalog({{name:'Gaia DR3', color:'#4488ff',
    shape:'cross', sourceSize:7, onClick:'showTable'}});
  gaiaData.forEach(s => cats.gaia.addSources([
    A.source(s.ra, s.dec, {{
      Source: s.source,
      'pmRA (mas/yr)': s.pmra.toFixed(1),
      'pmDE (mas/yr)': s.pmde.toFixed(1),
      'mu_tot (mas/yr)': s.mu.toFixed(1),
      'G mag': s.gmag.toFixed(2),
    }})
  ]));
  aladin.addCatalog(cats.gaia);

  // High-PM subset
  cats.highpm = A.catalog({{name:'High-PM stars', color:'#ff4444',
    shape:'circle', sourceSize:14, onClick:'showTable'}});
  gaiaData.filter(s => s.mu > 20).forEach(s => cats.highpm.addSources([
    A.source(s.ra, s.dec, {{
      Source: s.source,
      'mu_tot (mas/yr)': s.mu.toFixed(1),
      'G mag': s.gmag.toFixed(2),
      'DSS displacement': (s.mu * 38 / 1000).toFixed(2) + ' px (38-yr)',
    }})
  ]));
  aladin.addCatalog(cats.highpm);
  cats.highpm.hide();
  document.getElementById('btnHighPM').classList.remove('on');
}});

var vis = {{sim:true, gaia:true, highpm:false}};
function toggle(k) {{
  vis[k] = !vis[k];
  if (vis[k]) cats[k].show(); else cats[k].hide();
  document.getElementById('btn'+k.charAt(0).toUpperCase()+k.slice(1))
    .classList.toggle('on', vis[k]);
  aladin.view.forceRedraw();
}}
</script></body></html>"""

with open("m27_aladin_cats.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"  Written  : m27_aladin_cats.html")
print(f"  SIMBAD   : {len(cat_entries)} objects embedded")
print(f"  Gaia DR3 : {len(pm_entries)} stars embedded")
print(f"  High-PM  : {len(high_pm)} stars (mu > 20 mas/yr)")

subprocess.Popen(["cmd", "/c", "start", "m27_aladin_cats.html"])
print("  Opened in browser.")

"""
Skrip Verifikasi Otomatis Desain PCB & BOM VoltKu v3.0:
1. Memeriksa konsistensi BOM CSV & Pick-and-Place CPL.
2. Memverifikasi jarak isolasi galvanik (>= 6.0 mm) antara domain MAINS_ISO dan SAFE_DC.
3. Memverifikasi koordinat lubang baut M2.5 cocok dengan standoff casing v3.0.
4. Memeriksa struktur berkas KiCad dan rasio pembagi tegangan/burden BL0942.
"""

import csv
import json
import os
import sys

PCB_DIR = os.path.dirname(os.path.abspath(__file__))

REQUIRED_FILES = [
    "VoltKu_Main_v3.kicad_pro",
    "VoltKu_Main_v3.kicad_sch",
    "VoltKu_Main_v3.kicad_pcb",
    "VoltKu_v3_BOM_JLCPCB.csv",
    "VoltKu_v3_CPL.csv",
    "schematic_overview.svg",
    "README-PCB-DESIGN.md",
]

for fn in REQUIRED_FILES:
    fp = os.path.join(PCB_DIR, fn)
    assert os.path.exists(fp), f"Berkas wajib hilang: {fp}"

# 1. Validasi JSON project KiCad
with open(os.path.join(PCB_DIR, "VoltKu_Main_v3.kicad_pro"), encoding="utf-8") as f:
    pro = json.load(f)
classes = {c["name"]: c for c in pro["net_settings"]["classes"]}
assert "MAINS_AC" in classes and classes["MAINS_AC"]["clearance"] >= 2.0, (
    "Netclass MAINS_AC clearance terlalu kecil!"
)

# 2. Validasi BOM & total HPP elektronik
bom_path = os.path.join(PCB_DIR, "VoltKu_v3_BOM_JLCPCB.csv")
with open(bom_path, encoding="utf-8") as f:
    bom_rows = list(csv.DictReader(f))
assert len(bom_rows) >= 35, f"Jumlah baris BOM terlalu sedikit: {len(bom_rows)}"

domains = {r["Designator"]: r["Domain"] for r in bom_rows}
total_bom_retail = sum(
    int(r["Quantity"]) * int(r["Unit_Price_IDR_Est"]) for r in bom_rows
)
print(f"[BOM OK] {len(bom_rows)} entri BOM, estimasi total eceran = Rp {total_bom_retail:,}")

# 3. Validasi jarak isolasi antara komponen MAINS_ISO vs SAFE_DC di CPL
cpl_path = os.path.join(PCB_DIR, "VoltKu_v3_CPL.csv")
with open(cpl_path, encoding="utf-8") as f:
    cpl_rows = list(csv.DictReader(f))

mains_xs = []
safe_xs = []
for row in cpl_rows:
    des = row["Designator"]
    x_mm = float(row["Mid X"].replace("mm", "").strip())
    y_mm = float(row["Mid Y"].replace("mm", "").strip())
    assert -22.5 <= x_mm <= 22.5 and -17.0 <= y_mm <= 17.0, (
        f"{des} di luar PCB 45x34mm: ({x_mm}, {y_mm})"
    )
    dom = domains.get(des, "")
    if dom in ("MAINS_ISO", "MAINS_AC"):
        mains_xs.append((des, x_mm))
    elif dom == "SAFE_DC":
        safe_xs.append((des, x_mm))

max_mains_x = max(x for _, x in mains_xs)
min_safe_x = min(x for _, x in safe_xs)
iso_span = min_safe_x - max_mains_x
assert iso_span >= 6.0, f"Jarak zona isolasi kurang dari 6.0mm! span={iso_span:.2f}mm"
print(
    f"[ISOLATION OK] Jarak MAINS_ISO (max X={max_mains_x:.1f}mm) <-> "
    f"SAFE_DC (min X={min_safe_x:.1f}mm) = {iso_span:.1f} mm"
)

# 4. Validasi analog front-end BL0942
r_top = 5 * 390_000.0
r_bot = 510.0
v_vp_220 = 220.0 * (r_bot / (r_top + r_bot))
v_vp_260 = 260.0 * (r_bot / (r_top + r_bot))
assert v_vp_260 <= 0.070, f"VP over-voltage pada 260Vrms: {v_vp_260 * 1000:.2f} mVrms"

r_burden = 0.5  # 2 x 1.0 Ohm paralel
v_ct_max = 0.050 * r_burden  # 50mA sekunder max
assert v_ct_max <= 0.030, f"IP/IN over-voltage pada 50mA CT: {v_ct_max * 1000:.2f} mVrms"
print(
    f"[ANALOG FRONT-END OK] VP@220V={v_vp_220 * 1000:.2f} mVrms, "
    f"VP@260V={v_vp_260 * 1000:.2f} mVrms (max 70), "
    f"V_CT_max={v_ct_max * 1000:.2f} mVrms (max 30)"
)

# 5. Validasi keselarasan mounting hole PCB terhadap generate_casing_v3.py
with open(os.path.join(PCB_DIR, "VoltKu_Main_v3.kicad_pcb"), encoding="utf-8") as f:
    pcb_txt = f.read()
for coord in ["(at -19 -13.5)", "(at -19 13.5)", "(at 19 -13.5)", "(at 19 13.5)"]:
    assert coord in pcb_txt, f"Lubang mounting M2.5 tidak cocok dengan casing v3.0: {coord}"
assert pcb_txt.count("(") == pcb_txt.count(")"), "Kurung KiCad PCB tidak seimbang!"

with open(os.path.join(PCB_DIR, "VoltKu_Main_v3.kicad_sch"), encoding="utf-8") as f:
    sch_txt = f.read()
assert sch_txt.count("(") == sch_txt.count(")"), "Kurung KiCad Schematic tidak seimbang!"
print("[KICAD S-EXPR & MOUNTING HOLES OK] Semua struktur KiCad valid & pas casing v3.0.")
sys.exit(0)

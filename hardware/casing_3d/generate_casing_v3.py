"""
Script Generator 3D Casing v3.1 (Original Signature Design) - VoltKu Pro DIN-Rail
Desain industrial orisinal VoltKu (bukan tiruan bentuk kotak putih polos meteran pasaran):
1. Arsitektur Dual-Tone: Bodi bawah Charcoal Graphite bertekstur rusuk pendingin (fluted heat-sink ribs)
   dipadukan dengan mahkota muka Matte Titanium-Silver & sabuk aksen Electric Blue ciri khas VoltKu.
2. Muka "Cockpit Visor" simetris ber-chamfer oktagonal:
   - Layar TFT IPS 1.3" (240x240) diputar 90 derajat sehingga terpasang SIMETRIS DI TENGAH jendela DIN 45mm.
   - Di dagu bawah layar: tombol taktil model "Pill Rocker" cekung + bilah indikator cahaya kiri/kanan (PWR & WIFI).
   - Di mahkota atas layar: emblem timbul V-Crest VoltKu yang proporsional dan rapi.
3. Keamanan IP20 lebih baik: bahu terminal atas/bawah dilindungi tudung pengaman berlubang test-probe (terminal guard)
   serta kantong baut sudut M3 yang tenggelam rapi ke dalam rel rusuk samping.
4. Tetap kompatibel 100% dengan PCB Custom VoltKu v3.0 (45x34mm) & standar rel DIN 35mm 3-pole (54x90mm).
"""

import math
import os

import bmesh
import bpy
from mathutils import Vector

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(CURRENT_DIR, "export")
os.makedirs(EXPORT_DIR, exist_ok=True)

# 1. Reset scene & set unit milimeter
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 0.001
scene.unit_settings.length_unit = "MILLIMETERS"


def create_material(name, color_rgba, roughness=0.35, metallic=0.0, emission_rgba=None, emission_strength=0.0):
    mat = bpy.data.materials.new(name=name)
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color_rgba
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if emission_rgba and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = emission_rgba
        if emission_strength > 0.0 and "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


# Palet Orisinal VoltKu Signature Industrial Design
mat_graphite = create_material("Mat_VoltKu_Graphite", (0.13, 0.16, 0.22, 1.0), roughness=0.44)
mat_titanium = create_material("Mat_VoltKu_Titanium", (0.86, 0.89, 0.94, 1.0), roughness=0.28, metallic=0.12)
mat_visor_dark = create_material("Mat_VoltKu_SmokedVisor", (0.04, 0.06, 0.10, 1.0), roughness=0.14)
mat_navy = create_material("Mat_VoltKu_Navy", (0.05, 0.15, 0.36, 1.0), roughness=0.25)
mat_blue = create_material("Mat_VoltKu_ElectricBlue", (0.08, 0.48, 0.98, 1.0), roughness=0.22)
mat_amber = create_material("Mat_VoltKu_Amber", (0.97, 0.64, 0.05, 1.0), roughness=0.20)
mat_pcb_navy = create_material("Mat_Carrier_PCB", (0.04, 0.18, 0.36, 1.0), roughness=0.36)
mat_psu_black = create_material("Mat_HLK_PSU", (0.07, 0.08, 0.10, 1.0), roughness=0.45)
mat_term_green = create_material("Mat_Terminal_Green", (0.07, 0.44, 0.24, 1.0), roughness=0.40)
mat_brass = create_material("Mat_Brass", (0.86, 0.70, 0.24, 1.0), roughness=0.22, metallic=0.88)
mat_alu = create_material("Mat_Aluminum", (0.78, 0.82, 0.88, 1.0), roughness=0.24, metallic=0.85)
mat_ips_bg = create_material("Mat_IPS_Screen", (0.02, 0.05, 0.10, 1.0), roughness=0.10)
mat_ui_cyan = create_material(
    "Mat_IPS_Cyan", (0.18, 0.82, 0.99, 1.0), roughness=0.2,
    emission_rgba=(0.18, 0.82, 0.99, 1.0), emission_strength=2.3,
)
mat_ui_amber = create_material(
    "Mat_IPS_Amber", (0.99, 0.76, 0.16, 1.0), roughness=0.2,
    emission_rgba=(0.99, 0.76, 0.16, 1.0), emission_strength=2.4,
)
mat_ui_green = create_material(
    "Mat_IPS_Green", (0.18, 0.88, 0.50, 1.0), roughness=0.2,
    emission_rgba=(0.18, 0.88, 0.50, 1.0), emission_strength=2.2,
)
mat_studio = create_material("Mat_Studio_Floor", (0.07, 0.09, 0.14, 1.0), roughness=0.72)


def add_box(name, size_x, size_y, size_z, loc_x, loc_y, loc_z, rot_z=0.0, material=None):
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(loc_x, loc_y, loc_z),
        rotation=(0.0, 0.0, rot_z),
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size_x, size_y, size_z)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    return obj


def add_chamfered_box(
    name,
    size_x,
    size_y,
    size_z,
    corner_chamfer,
    chamfer_top=0.0,
    chamfer_bottom=0.0,
    segments=1,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=0.0,
    material=None,
):
    """Membuat balok ber-bevel oktagonal/chamfer khas desain industrial modern (bukan kotak polos)."""
    obj = add_box(name, size_x, size_y, size_z, loc_x, loc_y, loc_z, material=material)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()

    vert_edges = [
        e
        for e in bm.edges
        if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-4
        and abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-4
    ]
    if corner_chamfer > 0.05 and vert_edges:
        bmesh.ops.bevel(
            bm,
            geom=vert_edges,
            offset=corner_chamfer,
            offset_type="OFFSET",
            segments=segments,
            profile=0.5,
            affect="EDGES",
        )

    if chamfer_top > 0.05:
        bm.edges.ensure_lookup_table()
        half_z = size_z / 2.0
        top_edges = [
            e
            for e in bm.edges
            if abs(e.verts[0].co.z - half_z) < 1e-3 and abs(e.verts[1].co.z - half_z) < 1e-3
        ]
        if top_edges:
            bmesh.ops.bevel(
                bm,
                geom=top_edges,
                offset=chamfer_top,
                offset_type="OFFSET",
                segments=1,
                profile=0.5,
                affect="EDGES",
            )

    if chamfer_bottom > 0.05:
        bm.edges.ensure_lookup_table()
        half_z = -size_z / 2.0
        bot_edges = [
            e
            for e in bm.edges
            if abs(e.verts[0].co.z - half_z) < 1e-3 and abs(e.verts[1].co.z - half_z) < 1e-3
        ]
        if bot_edges:
            bmesh.ops.bevel(
                bm,
                geom=bot_edges,
                offset=chamfer_bottom,
                offset_type="OFFSET",
                segments=1,
                profile=0.5,
                affect="EDGES",
            )

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def add_cylinder(
    name,
    radius,
    depth,
    loc_x,
    loc_y,
    loc_z,
    rot_x=0.0,
    rot_y=0.0,
    rot_z=0.0,
    vertices=24,
    material=None,
):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=(loc_x, loc_y, loc_z),
        rotation=(rot_x, rot_y, rot_z),
    )
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    return obj


def add_cone(name, r1, r2, depth, loc_x, loc_y, loc_z, vertices=24, material=None):
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=r1,
        radius2=r2,
        depth=depth,
        location=(loc_x, loc_y, loc_z),
    )
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    return obj


def boolean_diff(target_obj, cutter_obj):
    mod = target_obj.modifiers.new(name="BoolDiff", type="BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter_obj
    mod.solver = "EXACT"
    bpy.context.view_layer.objects.active = target_obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter_obj, do_unlink=True)


def boolean_union(target_obj, tool_obj):
    mod = target_obj.modifiers.new(name="BoolUnion", type="BOOLEAN")
    mod.operation = "UNION"
    mod.object = tool_obj
    mod.solver = "EXACT"
    bpy.context.view_layer.objects.active = target_obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool_obj, do_unlink=True)


# ==========================================
# DIMENSI UTAMA VOLTKU SIGNATURE DIN-RAIL v3.1 (mm)
# ==========================================
BODY_W = 54.0        # X: standar lebar 3 modul DIN
BODY_H = 90.0        # Y: proporsi ergonomis dengan tudung terminal atas/bawah
BASE_D = 36.0        # Z: kedalaman wadah graphite
NOSE_H = 45.0        # Y: standar cutout tutup box MCB Indonesia
FLANGE_D = 5.5       # Z: bahu dengan alur tudung pengaman & alur garis biru
NOSE_D = 12.5        # Z: mahkota visor chamfered (total 36 + 5.5 + 12.5 = 54 mm)
WALL_T = 2.2
FLOOR_T = 2.4

inner_w = BODY_W - (2.0 * WALL_T)  # 49.6 mm
inner_h = BODY_H - (2.0 * WALL_T)  # 85.6 mm

DIN_RAIL_W = 35.6
DIN_SLOT_D = 7.6
DIN_BRIDGE_T = 2.2
CENTER_FLOOR_Z = DIN_SLOT_D + DIN_BRIDGE_T  # 9.8 mm

# ==========================================
# 1. CHASSIS BAWAH GRAPHITE (Sculpted Heatsink Sides)
# ==========================================
print("Mendesain VoltKu Signature Graphite Base v3.1...")

base_obj = add_chamfered_box(
    "V3_DIN_Bottom_Base",
    BODY_W,
    BODY_H,
    BASE_D,
    corner_chamfer=3.6,  # sudut berpotongan chamfer 45 derajat yang tegas
    chamfer_bottom=1.2,
    segments=1,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=BASE_D / 2.0,
    material=mat_graphite,
)

# Sirip pendingin vertikal (Fluted Heat-Sink Ribs) di kedua sisi kiri & kanan Base
for side_x in [-BODY_W / 2.0, BODY_W / 2.0]:
    for ry in [-30.0, -23.0, -16.0, -9.0, 9.0, 16.0, 23.0, 30.0]:
        fin = add_box(
            f"Side_Fin_{side_x}_{ry}",
            1.4,
            3.0,
            BASE_D - 9.0,
            side_x,
            ry,
            (BASE_D / 2.0) + 1.5,
        )
        boolean_diff(base_obj, fin)

# Rongga utama bagian atas Base
mid_cav_h = BASE_D - CENTER_FLOOR_Z + 3.0
mid_cutter = add_chamfered_box(
    "Base_Mid_Cutter",
    inner_w,
    inner_h,
    mid_cav_h,
    corner_chamfer=2.0,
    loc_z=CENTER_FLOOR_Z + (mid_cav_h / 2.0),
)
boolean_diff(base_obj, mid_cutter)

# Rongga dalam zona BAWAH (Terminal AC & Sekring) & zona ATAS (HLK-PM01 PSU)
low_bay_h = BASE_D - FLOOR_T + 2.0
for bay_name, cy, length in [("Low_Bay", -31.2, 23.2), ("Top_Bay", 31.2, 23.2)]:
    bc = add_box(bay_name, inner_w, length, low_bay_h, 0.0, cy, FLOOR_T + (low_bay_h / 2.0))
    boolean_diff(base_obj, bc)

# Kanal Rel DIN 35mm + kait atas + alur klip bawah
din_back_cut = add_box(
    "DIN_Channel_Main",
    BODY_W + 4.0,
    DIN_RAIL_W,
    DIN_SLOT_D + 0.2,
    0.0,
    0.0,
    (DIN_SLOT_D - 0.2) / 2.0,
)
boolean_diff(base_obj, din_back_cut)

upper_hook = add_box(
    "DIN_Upper_Hook",
    BODY_W - 6.0,
    2.4,
    2.0,
    0.0,
    (DIN_RAIL_W / 2.0) - 0.8,
    1.0,
    material=mat_graphite,
)
boolean_union(base_obj, upper_hook)

clip_track = add_box(
    "DIN_Clip_Track",
    16.6,
    22.0,
    3.6,
    0.0,
    -(DIN_RAIL_W / 2.0) - 6.0,
    1.7,
)
boolean_diff(base_obj, clip_track)

clip_t_slot = add_box(
    "DIN_Clip_TSlot",
    20.4,
    18.0,
    1.6,
    0.0,
    -(DIN_RAIL_W / 2.0) - 6.0,
    2.8,
)
boolean_diff(base_obj, clip_t_slot)

# Sekat Isolasi AC/DC
for sep_y, gap_x in [(-18.8, 14.0), (18.8, -14.0)]:
    sep_wall = add_box(
        f"Isolation_Wall_{sep_y}",
        inner_w,
        2.0,
        16.0,
        0.0,
        sep_y,
        CENTER_FLOOR_Z + 8.0,
        material=mat_graphite,
    )
    gap_cut = add_box(
        f"Isolation_Gap_{sep_y}",
        10.0,
        5.0,
        7.0,
        gap_x,
        sep_y,
        CENTER_FLOOR_Z + 13.5,
    )
    boolean_diff(sep_wall, gap_cut)
    boolean_union(base_obj, sep_wall)

# 4 Corner Bosses M3 di bahu luar
CORNER_X = 22.0
CORNER_Y = 39.8
boss_h = BASE_D - FLOOR_T
for cx, cy in [(-CORNER_X, -CORNER_Y), (-CORNER_X, CORNER_Y), (CORNER_X, -CORNER_Y), (CORNER_X, CORNER_Y)]:
    boss = add_cylinder(
        "Corner_Boss",
        3.5,
        boss_h,
        cx,
        cy,
        FLOOR_T + (boss_h / 2.0),
        vertices=18,
        material=mat_graphite,
    )
    boolean_union(base_obj, boss)
    hole = add_cylinder("Corner_Screw_Hole", 1.35, 16.0, cx, cy, BASE_D - 7.5, vertices=16)
    boolean_diff(base_obj, hole)

# 4 Standoff M2.5 Main Carrier PCB (45 x 34 mm, pitch 38 x 27 mm)
PCB_STAND_H = 10.2
for px in [-19.0, 19.0]:
    for py in [-13.5, 13.5]:
        pst = add_cylinder(
            "PCB_Standoff",
            2.8,
            PCB_STAND_H,
            px,
            py,
            CENTER_FLOOR_Z + (PCB_STAND_H / 2.0),
            vertices=18,
            material=mat_graphite,
        )
        boolean_union(base_obj, pst)
        phole = add_cylinder(
            "PCB_Screw_Hole",
            1.1,
            PCB_STAND_H + 1.0,
            px,
            py,
            CENTER_FLOOR_Z + (PCB_STAND_H / 2.0) + 0.5,
            vertices=14,
        )
        boolean_diff(base_obj, phole)

# Dudukan penahan HLK-PM01 di zona atas
for hx in [-18.2, 18.2]:
    rib = add_box(f"HLK_Stop_{hx}", 1.8, 16.0, 10.0, hx, 31.0, FLOOR_T + 5.0, material=mat_graphite)
    boolean_union(base_obj, rib)

# Sabuk Aksen Electric Blue (Signature Trim Ring) mengelilingi bibir atas Base (Z = 33.6 .. 35.8 mm)
accent_ring = add_chamfered_box(
    "Base_Blue_Accent_Belt",
    BODY_W + 0.6,
    BODY_H + 0.6,
    1.8,
    corner_chamfer=3.6,
    loc_z=BASE_D - 1.2,
    material=mat_blue,
)
ring_hole = add_chamfered_box(
    "Base_Belt_Hole",
    inner_w + 0.4,
    inner_h + 0.4,
    3.0,
    corner_chamfer=2.0,
    loc_z=BASE_D - 1.2,
)
boolean_diff(accent_ring, ring_hole)
base_obj.data.materials.append(mat_blue)
boolean_union(base_obj, accent_ring)

# Lubang kabel AC & soket CT bawah + ventilasi atas + port servis USB-C samping
for tx in [-11.0, -1.0]:
    ac_port = add_cylinder(
        f"AC_Wire_Port_{tx}",
        2.8,
        WALL_T * 4.5,
        tx,
        -BODY_H / 2.0,
        12.5,
        rot_x=math.radians(90.0),
        vertices=20,
    )
    boolean_diff(base_obj, ac_port)

ct_port = add_chamfered_box(
    "CT_Socket_Window",
    9.5,
    WALL_T * 4.5,
    7.5,
    corner_chamfer=1.0,
    loc_x=12.5,
    loc_y=-BODY_H / 2.0,
    loc_z=12.5,
)
boolean_diff(base_obj, ct_port)

for vx in [-12.0, -6.0, 0.0, 6.0, 12.0]:
    top_vent = add_chamfered_box(
        f"Top_Vent_{vx}",
        2.4,
        WALL_T * 4.5,
        8.5,
        corner_chamfer=0.8,
        loc_x=vx,
        loc_y=BODY_H / 2.0,
        loc_z=15.0,
    )
    boolean_diff(base_obj, top_vent)

usbc_cut = add_chamfered_box(
    "Service_USBC_Window",
    WALL_T * 4.5,
    10.5,
    5.0,
    corner_chamfer=1.0,
    loc_x=BODY_W / 2.0,
    loc_y=6.0,
    loc_z=23.5,
)
boolean_diff(base_obj, usbc_cut)

# ==========================================
# 2. DIN RAIL SNAP CLIP
# ==========================================
print("Mendesain DIN Rail Snap Clip v3.1...")
din_clip = add_chamfered_box(
    "V3_DIN_Rail_Clip",
    16.0,
    24.0,
    3.2,
    corner_chamfer=1.2,
    loc_y=-(DIN_RAIL_W / 2.0) - 6.0,
    loc_z=1.6,
    material=mat_blue,
)
clip_wing = add_box("DIN_Clip_T_Wing", 19.6, 14.0, 1.2, 0.0, -(DIN_RAIL_W / 2.0) - 5.0, 2.6, material=mat_blue)
boolean_union(din_clip, clip_wing)
clip_nose = add_box("DIN_Clip_Catch", 15.8, 3.2, 2.2, 0.0, -(DIN_RAIL_W / 2.0) + 0.8, 1.1, material=mat_blue)
boolean_union(din_clip, clip_nose)
clip_pull_hole = add_box("DIN_Clip_Pull_Slot", 6.0, 3.5, 4.0, 0.0, -(DIN_RAIL_W / 2.0) - 15.0, 1.6)
boolean_diff(din_clip, clip_pull_hole)

# ==========================================
# 3. TOP LID ORISINAL: TITANIUM CROWN + SYMMETRIC COCKPIT VISOR
# ==========================================
print("Mendesain VoltKu Signature Titanium Lid v3.1...")

LID_Z_OFFSET = BASE_D + 11.0  # posisi exploded preview

# 3a. Pelat Bahu Titanium dengan Tudung Pelindung Terminal IP20
lid_flange = add_chamfered_box(
    "V3_DIN_Top_Lid",
    BODY_W,
    BODY_H,
    FLANGE_D,
    corner_chamfer=3.6,
    chamfer_top=1.0,
    segments=1,
    loc_z=LID_Z_OFFSET + (FLANGE_D / 2.0),
    material=mat_titanium,
)

# Alur rusuk arsitektur horizontal di bahu atas & bawah agar tidak polos seperti DIN meter biasa
for sy in [-38.5, -31.5, 31.5, 38.5]:
    groove = add_box(f"Shoulder_Rib_{sy}", BODY_W - 14.0, 1.8, 1.2, 0.0, sy, LID_Z_OFFSET + FLANGE_D - 0.3)
    boolean_diff(lid_flange, groove)

# 3b. Menara Muka Cockpit Visor 45mm dengan Chamfer Tegas (Oktagonal Mewah)
nose_total_z = FLANGE_D + NOSE_D
lid_nose = add_chamfered_box(
    "Lid_Cockpit_Crown",
    BODY_W - 0.8,
    NOSE_H,
    NOSE_D + 1.0,
    corner_chamfer=4.5,  # chamfer 4.5mm membentuk bingkai visor oktagonal khas VoltKu
    chamfer_top=1.8,
    segments=1,
    loc_z=LID_Z_OFFSET + FLANGE_D + (NOSE_D / 2.0) - 0.5,
    material=mat_titanium,
)
boolean_union(lid_flange, lid_nose)
lid_obj = lid_flange

# Rongga dalam menara Lid (muat lega TFT 1.3" diputar 90 deg = 39 x 27.8 mm)
lid_cav = add_chamfered_box(
    "Lid_Inner_Cavity",
    inner_w - 1.4,
    NOSE_H - 4.4,
    NOSE_D + 1.5,
    corner_chamfer=2.0,
    loc_z=LID_Z_OFFSET + ((NOSE_D + 1.5) / 2.0) - 0.5,
)
boolean_diff(lid_obj, lid_cav)

# Bibir pengunci ke Base
lip_outer = add_chamfered_box(
    "Lid_Lip_Outer",
    inner_w - 0.6,
    inner_h - 0.6,
    2.2,
    corner_chamfer=2.0,
    loc_z=LID_Z_OFFSET - 1.0,
    material=mat_titanium,
)
lip_inner = add_chamfered_box(
    "Lid_Lip_Inner",
    inner_w - 3.4,
    inner_h - 3.4,
    3.6,
    corner_chamfer=1.6,
    loc_z=LID_Z_OFFSET - 1.0,
)
boolean_diff(lip_outer, lip_inner)
boolean_union(lid_obj, lip_outer)

# 4 Lubang Baut M3 Countersunk di kantong bahu (pakai baut M3 x 16mm -> masuk 10.5mm ke Base)
for cx, cy in [(-CORNER_X, -CORNER_Y), (-CORNER_X, CORNER_Y), (CORNER_X, -CORNER_Y), (CORNER_X, CORNER_Y)]:
    bolt_thru = add_cylinder("Lid_Bolt_Hole", 1.65, FLANGE_D + 4.0, cx, cy, LID_Z_OFFSET + (FLANGE_D / 2.0), vertices=18)
    boolean_diff(lid_obj, bolt_thru)
    bolt_csink = add_cone("Lid_Bolt_Csink", 1.65, 3.1, 2.2, cx, cy, LID_Z_OFFSET + FLANGE_D - 1.0, vertices=20)
    boolean_diff(lid_obj, bolt_csink)

# 2 Lubang Probe / Obeng Terminal AC tersembunyi rapi di bahu bawah
for tx in [-11.0, -1.0]:
    screw_access = add_cylinder("Terminal_Screw_Access", 2.4, FLANGE_D + 4.0, tx, -34.5, LID_Z_OFFSET + (FLANGE_D / 2.0), vertices=18)
    boolean_diff(lid_obj, screw_access)

# Ceruk Kaca Visor Gelap Oktagonal di muka depan
lid_front_z = LID_Z_OFFSET + nose_total_z
visor_pocket = add_chamfered_box(
    "Front_Visor_Recess",
    45.6,
    38.4,
    1.8,
    corner_chamfer=3.6,
    loc_z=lid_front_z,
)
boolean_diff(lid_obj, visor_pocket)

# Jendela Layar TFT IPS 1.3" SIMETRIS DI TENGAH ATAS (IPS_X = 0.0, IPS_Y = +5.2)
IPS_X = 0.0
IPS_Y = 5.2
ips_window = add_chamfered_box(
    "TFT_IPS_Window",
    24.4,
    24.4,
    8.0,
    corner_chamfer=1.6,
    loc_x=IPS_X,
    loc_y=IPS_Y,
    loc_z=lid_front_z - 2.0,
)
boolean_diff(lid_obj, ips_window)

# Dagu Bawah Simetris: Tombol Taktil Model "Pill Rocker" (X = 0.0, Y = -13.0)
BTN_Y = -13.0
btn_slot = add_chamfered_box(
    "Pill_Button_Slot",
    13.0,
    5.2,
    8.0,
    corner_chamfer=2.0,
    loc_x=0.0,
    loc_y=BTN_Y,
    loc_z=lid_front_z - 2.0,
)
boolean_diff(lid_obj, btn_slot)

# 2 Bilah Indikator Cahaya Simetris Kiri & Kanan Tombol (PWR amber kiri, WIFI biru kanan)
for lx in [-13.5, 13.5]:
    bar_slot = add_chamfered_box(
        f"LED_Bar_Slot_{lx}",
        6.0,
        2.2,
        8.0,
        corner_chamfer=0.8,
        loc_x=lx,
        loc_y=BTN_Y,
        loc_z=lid_front_z - 2.0,
    )
    boolean_diff(lid_obj, bar_slot)

# Tambahkan material aksen pada Lid
for m in (mat_visor_dark, mat_navy, mat_blue, mat_amber):
    lid_obj.data.materials.append(m)

# Pelat Visor Smoked Dark Oktagonal
visor_plate = add_chamfered_box(
    "Front_Visor_Plate",
    45.0,
    37.8,
    0.8,
    corner_chamfer=3.4,
    loc_z=lid_front_z - 0.55,
    material=mat_visor_dark,
)
for cname, sx, sy, cr, cx, cy in [
    ("vp_ips", 24.4, 24.4, 1.6, IPS_X, IPS_Y),
    ("vp_btn", 13.0, 5.2, 2.0, 0.0, BTN_Y),
    ("vp_l1", 6.0, 2.2, 0.8, -13.5, BTN_Y),
    ("vp_l2", 6.0, 2.2, 0.8, 13.5, BTN_Y),
]:
    c = add_chamfered_box(cname, sx, sy, 4.0, corner_chamfer=cr, loc_x=cx, loc_y=cy, loc_z=lid_front_z - 0.55)
    boolean_diff(visor_plate, c)
boolean_union(lid_obj, visor_plate)

# 4 Boss Internal untuk Modul TFT IPS 1.3" (diputar 90 deg -> 39.0 x 27.8 mm, pitch 34.0 x 23.0 mm)
tft_stand_h = 3.2
for tx_off in [-17.0, 17.0]:
    for ty_off in [-11.5, 11.5]:
        tpost = add_cylinder(
            "TFT_Mount_Boss",
            2.0,
            tft_stand_h,
            IPS_X + tx_off,
            IPS_Y + ty_off,
            lid_front_z - 2.0 - (tft_stand_h / 2.0),
            vertices=14,
            material=mat_titanium,
        )
        boolean_union(lid_obj, tpost)
        thole = add_cylinder(
            "TFT_Mount_Hole",
            0.85,
            tft_stand_h + 1.0,
            IPS_X + tx_off,
            IPS_Y + ty_off,
            lid_front_z - 2.0 - (tft_stand_h / 2.0) - 0.5,
            vertices=12,
        )
        boolean_diff(lid_obj, thole)

# Emblem Signature VoltKu V-Crest di Mahkota Atas (X = 0.0, Y = +19.8 mm, di atas kaca visor)
emblem_z = lid_front_z - 0.05
v_left = add_chamfered_box("V31_V_Left", 1.7, 4.4, 0.6, 0.4, loc_x=-1.2, loc_y=19.8, loc_z=emblem_z, material=mat_navy)
v_left.rotation_euler = (0.0, 0.0, math.radians(24.0))
bpy.context.view_layer.objects.active = v_left
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

v_right = add_chamfered_box("V31_V_Right", 1.7, 4.4, 0.6, 0.4, loc_x=1.2, loc_y=19.8, loc_z=emblem_z, material=mat_blue)
v_right.rotation_euler = (0.0, 0.0, math.radians(-24.0))
bpy.context.view_layer.objects.active = v_right
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

v_dot = add_cylinder("V31_Energy_Dot", 0.75, 0.6, 0.0, 21.4, emblem_z, vertices=16, material=mat_amber)
for vp in (v_left, v_right, v_dot):
    boolean_union(lid_obj, vp)

# ==========================================
# 4. KOMPONEN ELEKTRONIK REFERENSI & SIMULASI COCKPIT IPS
# ==========================================
print("Menambahkan Referensi Elektronik Internal & UI IPS Simetris...")

hlk_box = add_chamfered_box("Ref_HLK_PM01", 34.0, 20.0, 15.0, 1.0, loc_x=0.0, loc_y=31.0, loc_z=FLOOR_T + 7.5, material=mat_psu_black)
ac_term = add_box("Ref_AC_Terminal", 18.0, 11.0, 11.5, -6.0, -34.5, FLOOR_T + 6.0, material=mat_term_green)
s_l = add_cylinder("Ref_Screw_L", 2.1, 2.0, -11.0, -34.5, FLOOR_T + 11.8, vertices=16, material=mat_brass)
s_n = add_cylinder("Ref_Screw_N", 2.1, 2.0, -1.0, -34.5, FLOOR_T + 11.8, vertices=16, material=mat_brass)
ct_conn = add_box("Ref_CT_Connector", 8.5, 10.0, 7.0, 12.5, -35.5, FLOOR_T + 4.5, material=mat_graphite)

pcb_z = CENTER_FLOOR_Z + PCB_STAND_H + 0.8
main_pcb = add_box("Ref_Main_Carrier_PCB", 45.0, 34.0, 1.6, 0.0, 0.0, pcb_z, material=mat_pcb_navy)
esp_c3 = add_box("Ref_ESP32_C3_SuperMini", 18.0, 22.5, 3.8, 12.5, 4.0, pcb_z + 2.7, material=mat_alu)
bl0942_ic = add_box("Ref_BL0942_IC", 5.0, 4.0, 1.2, -11.0, -6.0, pcb_z + 1.4, material=mat_psu_black)

# Tombol Pill Rocker + LED Bars yang menyala lembut di dagu layar
pill_btn = add_chamfered_box("Ref_Pill_Button", 12.0, 4.4, 2.2, 1.8, loc_x=0.0, loc_y=BTN_Y, loc_z=lid_front_z - 0.5, material=mat_blue)
led_bar_l = add_chamfered_box("Ref_LED_PWR", 5.2, 1.6, 1.4, 0.6, loc_x=-13.5, loc_y=BTN_Y, loc_z=lid_front_z - 0.7, material=mat_ui_amber)
led_bar_r = add_chamfered_box("Ref_LED_WIFI", 5.2, 1.6, 1.4, 0.6, loc_x=13.5, loc_y=BTN_Y, loc_z=lid_front_z - 0.7, material=mat_ui_cyan)

# TFT IPS 1.3" (diputar 90 deg -> 39.0 x 27.8 mm) simetris di X=0, Y=+5.2
tft_pcb = add_box("Ref_TFT_IPS_PCB_Rot90", 39.0, 27.8, 1.6, IPS_X, IPS_Y, lid_front_z - 5.2, material=mat_pcb_navy)
ips_panel = add_box("Ref_TFT_Glass", 24.0, 24.0, 0.5, IPS_X, IPS_Y, lid_front_z - 1.1, material=mat_ips_bg)

# Simulasi UI IPS menyala simetris (Watt besar + Rupiah + Volt/Ampere + Bar Status)
ui_pwr = add_chamfered_box("UI_Power", 16.5, 3.8, 0.2, 0.4, loc_x=IPS_X, loc_y=IPS_Y + 6.6, loc_z=lid_front_z - 0.8, material=mat_ui_amber)
ui_rp = add_chamfered_box("UI_Rupiah", 14.5, 2.4, 0.2, 0.3, loc_x=IPS_X, loc_y=IPS_Y + 1.8, loc_z=lid_front_z - 0.8, material=mat_ui_green)
ui_v = add_chamfered_box("UI_Volt", 8.6, 2.0, 0.2, 0.3, loc_x=IPS_X - 5.0, loc_y=IPS_Y - 3.0, loc_z=lid_front_z - 0.8, material=mat_ui_cyan)
ui_a = add_chamfered_box("UI_Amp", 8.6, 2.0, 0.2, 0.3, loc_x=IPS_X + 5.0, loc_y=IPS_Y - 3.0, loc_z=lid_front_z - 0.8, material=mat_ui_cyan)
ui_bar = add_chamfered_box("UI_Bar", 18.0, 2.2, 0.2, 0.5, loc_x=IPS_X, loc_y=IPS_Y - 7.6, loc_z=lid_front_z - 0.8, material=mat_ui_green)

# ==========================================
# 5. VALIDASI CLEARANCE OTOMATIS
# ==========================================
def check_bounds(obj, name, max_x=BODY_W / 2.0 - WALL_T, max_y=BODY_H / 2.0 - WALL_T):
    xs = [(obj.matrix_world @ v.co).x for v in obj.data.vertices]
    ys = [(obj.matrix_world @ v.co).y for v in obj.data.vertices]
    zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
    min_x, max_vx = min(xs), max(xs)
    min_y, max_vy = min(ys), max(ys)
    min_z, max_vz = min(zs), max(zs)
    assert min_x >= -max_x and max_vx <= max_x, f"{name} keluar batas X: {min_x:.2f}..{max_vx:.2f}"
    assert min_y >= -max_y and max_vy <= max_y, f"{name} keluar batas Y: {min_y:.2f}..{max_vy:.2f}"
    print(f"[FIT CHECK OK] {name}: X[{min_x:.1f}..{max_vx:.1f}] Y[{min_y:.1f}..{max_vy:.1f}] Z[{min_z:.1f}..{max_vz:.1f}]")

for ref_obj, ref_name in [
    (hlk_box, "HLK-PM01 PSU"),
    (ac_term, "AC Screw Terminal"),
    (main_pcb, "Main Carrier PCB"),
    (esp_c3, "ESP32-C3 SuperMini"),
    (tft_pcb, "TFT 1.3 IPS Rotated 90deg"),
]:
    check_bounds(ref_obj, ref_name)

# ==========================================
# 6. ORGANISASI KOLEKSI & EKSPOR STL SIAP CETAK
# ==========================================
def move_to_collection(obj, coll_name):
    coll = bpy.data.collections.get(coll_name)
    if not coll:
        coll = bpy.data.collections.new(coll_name)
        bpy.context.scene.collection.children.link(coll)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)


move_to_collection(base_obj, "Enclosure_Base_V3")
move_to_collection(lid_obj, "Enclosure_Lid_V3")
move_to_collection(din_clip, "Enclosure_Clip_V3")
for dummy in [
    hlk_box, ac_term, s_l, s_n, ct_conn, main_pcb, esp_c3, bl0942_ic,
    pill_btn, led_bar_l, led_bar_r, tft_pcb, ips_panel, ui_pwr, ui_rp, ui_v, ui_a, ui_bar,
]:
    move_to_collection(dummy, "Electronics_Reference_V3")


def export_selected_stl(objects_to_export, filepath, orient_lid_down=False):
    temp_copies = []
    for o in objects_to_export:
        dup = o.copy()
        dup.data = o.data.copy()
        bpy.context.scene.collection.objects.link(dup)
        temp_copies.append(dup)

    bpy.ops.object.select_all(action="DESELECT")
    for dup in temp_copies:
        dup.select_set(True)
    bpy.context.view_layer.objects.active = temp_copies[0]

    if orient_lid_down:
        for dup in temp_copies:
            dup.rotation_euler = (math.radians(180.0), 0.0, 0.0)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        min_wz = min((dup.matrix_world @ v.co).z for dup in temp_copies for v in dup.data.vertices)
        for dup in temp_copies:
            dup.location.z -= min_wz

    bpy.ops.wm.stl_export(filepath=filepath, export_selected_objects=True)
    wzs = [(dup.matrix_world @ v.co).z for dup in temp_copies for v in dup.data.vertices]
    print(f"-> STL diekspor: {filepath} (Z: {min(wzs):.2f} .. {max(wzs):.2f} mm)")

    for dup in temp_copies:
        mesh = dup.data
        bpy.data.objects.remove(dup, do_unlink=True)
        bpy.data.meshes.remove(mesh, do_unlink=True)


export_selected_stl([base_obj], os.path.join(EXPORT_DIR, "v3_din_bottom_base.stl"), orient_lid_down=False)
export_selected_stl([lid_obj], os.path.join(EXPORT_DIR, "v3_din_top_lid.stl"), orient_lid_down=True)
export_selected_stl([din_clip], os.path.join(EXPORT_DIR, "v3_din_rail_clip.stl"), orient_lid_down=False)
export_selected_stl([base_obj, lid_obj, din_clip], os.path.join(EXPORT_DIR, "v3_din_assembly_preview.stl"), orient_lid_down=False)

# ==========================================
# 7. STUDIO RENDER PRODUCT SHOWCASE ORISINAL v3.1
# ==========================================
print("Menyiapkan Studio Render VoltKu Signature v3.1...")

bpy.ops.mesh.primitive_plane_add(size=1600.0, location=(0.0, 0.0, -0.5))
floor_plane = bpy.context.active_object
floor_plane.name = "Studio_Backdrop"
floor_plane.data.materials.append(mat_studio)
move_to_collection(floor_plane, "Studio_Setup")

world = bpy.data.worlds.new("VoltKu_V3_Studio")
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs[0].default_value = (0.07, 0.09, 0.14, 1.0)
    bg_node.inputs[1].default_value = 0.55

bpy.ops.object.light_add(type="SUN", location=(115.0, -135.0, 200.0))
sun_key = bpy.context.active_object
sun_key.name = "Studio_Sun_Key"
sun_key.data.energy = 2.9
sun_key.data.angle = math.radians(10.0)
sun_key.data.color = (1.0, 0.99, 0.96)
sun_key.rotation_euler = (math.radians(38.0), math.radians(14.0), math.radians(36.0))
move_to_collection(sun_key, "Studio_Setup")

bpy.ops.object.light_add(type="AREA", location=(-130.0, 95.0, 125.0))
fill_light = bpy.context.active_object
fill_light.name = "Studio_Fill"
fill_light.data.energy = 11.5
fill_light.data.size = 150.0
fill_light.data.color = (0.76, 0.88, 1.0)
fill_light.rotation_euler = (Vector((0.0, 0.0, 28.0)) - fill_light.location).to_track_quat("-Z", "Y").to_euler()
move_to_collection(fill_light, "Studio_Setup")

bpy.ops.object.light_add(type="AREA", location=(15.0, 145.0, 145.0))
rim_light = bpy.context.active_object
rim_light.name = "Studio_Rim"
rim_light.data.energy = 15.0
rim_light.data.size = 140.0
rim_light.data.color = (0.94, 0.98, 1.0)
rim_light.rotation_euler = (Vector((0.0, 0.0, 32.0)) - rim_light.location).to_track_quat("-Z", "Y").to_euler()
move_to_collection(rim_light, "Studio_Setup")

bpy.ops.object.camera_add(location=(96.0, -112.0, 126.0))
cam = bpy.context.active_object
cam.name = "Main_Camera"
cam.rotation_euler = (Vector((0.0, -1.5, 34.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 45.0
scene.camera = cam
move_to_collection(cam, "Studio_Setup")

scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1440
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = "PNG"
preview_v3_path = os.path.join(CURRENT_DIR, "render_preview_v3.png")
scene.render.filepath = preview_v3_path

bpy.ops.render.render(write_still=True)
print(f"-> Render preview v3.1 tersimpan di: {preview_v3_path}")

blend_v3_path = os.path.join(CURRENT_DIR, "energy_monitor_v3.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_v3_path)
print(f"-> File Blender v3.1 tersimpan di: {blend_v3_path}")

"""
Script Generator 3D Casing v3.0 - VoltKu Pro DIN-Rail Smart Energy Monitor
Dirancang untuk menyaingi & mengungguli meteran DIN-Rail komersial (kelas DSZ-2066 / AT4PW):
1. Form factor standar MCB 3-Pole DIN-Rail 35mm (54.0 x 88.0 x 52.0 mm) dengan bahu 45mm pas jendela panel MCB rumah.
2. Layar warna TFT IPS 1.3" (240x240 ST7789) di bezel depan gelap + tombol taktil PAIR/HALAMAN + emblem 3D V-Crest VoltKu.
3. Catu daya AC-DC terisolasi internal (HLK-PM01 5V) + blok terminal sekrup AC 220V & soket CT 2-pin di sisi bawah (tanpa charger HP eksternal!).
4. MCU ringkas ESP32-C3 SuperMini + Custom Metering Carrier PCB (BL0942 / ADE7953) dengan dinding isolasi AC/DC >= 6mm.
5. Printable 100% tanpa support: Base (Z=0), Top Lid telungkup rata (Z=0), dan DIN Rail Snap Clip (Z=0).
"""

import math
import os
import bpy
import bmesh
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


# Palet material produk komersial VoltKu v3.0
mat_white_body = create_material("Mat_VoltKu_WhiteShell", (0.93, 0.95, 0.98, 1.0), roughness=0.32)
mat_slate_clip = create_material("Mat_VoltKu_SlateClip", (0.16, 0.21, 0.29, 1.0), roughness=0.40)
mat_bezel_dark = create_material("Mat_VoltKu_DarkBezel", (0.04, 0.06, 0.10, 1.0), roughness=0.18)
mat_navy = create_material("Mat_VoltKu_Navy", (0.05, 0.14, 0.34, 1.0), roughness=0.25)
mat_blue = create_material("Mat_VoltKu_Blue", (0.09, 0.48, 0.98, 1.0), roughness=0.22)
mat_amber = create_material("Mat_VoltKu_Amber", (0.97, 0.64, 0.05, 1.0), roughness=0.20)
mat_pcb_navy = create_material("Mat_Carrier_PCB", (0.04, 0.18, 0.36, 1.0), roughness=0.36)
mat_psu_black = create_material("Mat_HLK_PSU", (0.07, 0.08, 0.10, 1.0), roughness=0.45)
mat_term_green = create_material("Mat_Terminal_Green", (0.07, 0.44, 0.24, 1.0), roughness=0.40)
mat_brass = create_material("Mat_Brass", (0.86, 0.70, 0.24, 1.0), roughness=0.22, metallic=0.88)
mat_alu = create_material("Mat_Aluminum", (0.78, 0.82, 0.88, 1.0), roughness=0.24, metallic=0.85)
mat_ips_bg = create_material("Mat_IPS_Screen", (0.03, 0.06, 0.12, 1.0), roughness=0.12)
mat_ui_cyan = create_material(
    "Mat_IPS_Cyan", (0.15, 0.78, 0.98, 1.0), roughness=0.2,
    emission_rgba=(0.15, 0.78, 0.98, 1.0), emission_strength=2.2,
)
mat_ui_amber = create_material(
    "Mat_IPS_Amber", (0.98, 0.75, 0.14, 1.0), roughness=0.2,
    emission_rgba=(0.98, 0.75, 0.14, 1.0), emission_strength=2.2,
)
mat_ui_green = create_material(
    "Mat_IPS_Green", (0.16, 0.86, 0.48, 1.0), roughness=0.2,
    emission_rgba=(0.16, 0.86, 0.48, 1.0), emission_strength=2.2,
)
mat_studio = create_material("Mat_Studio_Floor", (0.08, 0.10, 0.15, 1.0), roughness=0.72)


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


def add_rounded_box(
    name,
    size_x,
    size_y,
    size_z,
    radius,
    loc_x,
    loc_y,
    loc_z,
    chamfer_top=0.0,
    chamfer_bottom=0.0,
    segments=5,
    material=None,
):
    """Membuat balok solid dengan sudut vertikal membulat dan chamfer atas/bawah opsional."""
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
    if radius > 0.05 and vert_edges:
        bmesh.ops.bevel(
            bm,
            geom=vert_edges,
            offset=radius,
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
                segments=2,
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
                segments=2,
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
# DIMENSI UTAMA CASING DIN-RAIL v3.0 (mm)
# Standar 3-Pole MCB: Lebar 54 mm, Tinggi 88 mm, Bahu 45 mm
# ==========================================
BODY_W = 54.0        # X: 3 modul DIN (3 x 18mm)
BODY_H = 88.0        # Y: tinggi MCB standar
BASE_D = 36.0        # Z: kedalaman wadah bawah (dari rel DIN ke atas flange)
NOSE_H = 45.0        # Y: standar cutout tutup box panel MCB Indonesia
FLANGE_D = 4.0       # Z: ketebalan bahu bawah/atas lid
NOSE_D = 12.0        # Z: tonjolan muka bezel depan (total kedalaman 36 + 4 + 12 = 52 mm)
CORNER_R = 2.6
WALL_T = 2.2
FLOOR_T = 2.4

inner_w = BODY_W - (2.0 * WALL_T)  # 49.6 mm
inner_h = BODY_H - (2.0 * WALL_T)  # 83.6 mm
inner_r = 1.4

DIN_RAIL_W = 35.6    # rel DIN 35mm + 0.6mm clearance
DIN_SLOT_D = 7.6     # kedalaman kanal belakang untuk rel 35mm
DIN_BRIDGE_T = 2.2   # tebal lantai di atas kanal DIN (lantai zona tengah di Z = 9.8mm)
CENTER_FLOOR_Z = DIN_SLOT_D + DIN_BRIDGE_T  # 9.8 mm

# ==========================================
# 1. ENCLOSURE BOTTOM BASE (Wadah DIN-Rail)
# ==========================================
print("Mendesain VoltKu DIN-Rail Base v3.0...")

base_obj = add_rounded_box(
    "V3_DIN_Bottom_Base",
    BODY_W,
    BODY_H,
    BASE_D,
    radius=CORNER_R,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=BASE_D / 2.0,
    chamfer_bottom=0.8,
    segments=4,
    material=mat_white_body,
)

# Rongga utama bagian atas Base (Z = CENTER_FLOOR_Z .. BASE_D)
mid_cav_h = BASE_D - CENTER_FLOOR_Z + 3.0
mid_cutter = add_rounded_box(
    "Base_Mid_Cutter",
    inner_w,
    inner_h,
    mid_cav_h,
    radius=inner_r,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=CENTER_FLOOR_Z + (mid_cav_h / 2.0),
    segments=4,
)
boolean_diff(base_obj, mid_cutter)

# Rongga lebih dalam di zona BAWAH (Y = -41.8 .. -19.5 mm) untuk blok terminal AC & sekring
low_bay_y1, low_bay_y2 = -41.8, -19.5
low_bay_cy = (low_bay_y1 + low_bay_y2) / 2.0
low_bay_len = low_bay_y2 - low_bay_y1
low_bay_h = BASE_D - FLOOR_T + 2.0
low_cutter = add_box(
    "Base_Low_Bay",
    inner_w,
    low_bay_len,
    low_bay_h,
    0.0,
    low_bay_cy,
    FLOOR_T + (low_bay_h / 2.0),
)
boolean_diff(base_obj, low_cutter)

# Rongga lebih dalam di zona ATAS (Y = +19.5 .. +41.8 mm) untuk modul PSU HLK-PM01 (34 x 20.2 x 15 mm)
top_bay_y1, top_bay_y2 = 19.5, 41.8
top_bay_cy = (top_bay_y1 + top_bay_y2) / 2.0
top_bay_len = top_bay_y2 - top_bay_y1
top_cutter = add_box(
    "Base_Top_Bay",
    inner_w,
    top_bay_len,
    low_bay_h,
    0.0,
    top_bay_cy,
    FLOOR_T + (low_bay_h / 2.0),
)
boolean_diff(base_obj, top_cutter)

# Kanal Rel DIN 35mm di bagian belakang Base (Z = 0 .. DIN_SLOT_D)
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

# Bibir pengait atas pada rel DIN (kait tetap 1.8mm menjorok ke bawah di sisi Y = +17.8mm)
upper_hook = add_box(
    "DIN_Upper_Hook",
    BODY_W,
    2.4,
    2.0,
    0.0,
    (DIN_RAIL_W / 2.0) - 0.8,
    1.0,
    material=mat_white_body,
)
boolean_union(base_obj, upper_hook)

# Alur slider klip DIN bawah (Y = -17.8 .. -32.0 mm, kedalaman 3.4mm) agar v3_din_rail_clip.stl bisa diklik!
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

# T-slot pengunci klip DIN
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

# Dinding sekat isolasi AC/DC di dalam Base:
# Memisahkan zona bawah (Terminal AC & Sekring) dan zona atas (HLK-PM01) dari zona logika tengah
for sep_y, gap_x in [(-18.5, 14.0), (18.5, -14.0)]:
    sep_wall = add_box(
        f"Isolation_Wall_{sep_y}",
        inner_w,
        2.0,
        16.0,
        0.0,
        sep_y,
        CENTER_FLOOR_Z + 8.0,
        material=mat_white_body,
    )
    # Celah kecil hanya untuk kabel DC 5V / jalur CT terisolasi
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

# 4 Corner Screw Bosses pada Base di bahu luar jendela 45mm (X = ±22.4, Y = ±38.8)
# Tinggi boss tepat rata top rim Base (Z = BASE_D = 36.0 mm)
CORNER_X = 22.4
CORNER_Y = 38.8
boss_h = BASE_D - FLOOR_T
for cx, cy in [
    (-CORNER_X, -CORNER_Y),
    (-CORNER_X, CORNER_Y),
    (CORNER_X, -CORNER_Y),
    (CORNER_X, CORNER_Y),
]:
    boss = add_cylinder(
        "Corner_Boss",
        radius=3.5,
        depth=boss_h,
        loc_x=cx,
        loc_y=cy,
        loc_z=FLOOR_T + (boss_h / 2.0),
        vertices=20,
        material=mat_white_body,
    )
    boolean_union(base_obj, boss)
    hole = add_cylinder(
        "Corner_Screw_Hole",
        radius=1.35,  # M3 self-tapping
        depth=16.0,
        loc_x=cx,
        loc_y=cy,
        loc_z=BASE_D - 7.5,
        vertices=16,
    )
    boolean_diff(base_obj, hole)

# 4 Standoff M2.5 untuk Main Carrier PCB (44 x 33 mm) di zona tengah (Z_pcb = 20.0 mm)
PCB_STAND_H = 10.2  # CENTER_FLOOR_Z (9.8) + 10.2 = 20.0 mm
for px in [-19.0, 19.0]:  # pitch X = 38 mm
    for py in [-13.5, 13.5]:  # pitch Y = 27 mm
        pst = add_cylinder(
            "PCB_Standoff",
            radius=2.8,
            depth=PCB_STAND_H,
            loc_x=px,
            loc_y=py,
            loc_z=CENTER_FLOOR_Z + (PCB_STAND_H / 2.0),
            vertices=18,
            material=mat_white_body,
        )
        boolean_union(base_obj, pst)
        phole = add_cylinder(
            "PCB_Screw_Hole",
            radius=1.1,  # M2.5
            depth=PCB_STAND_H + 1.0,
            loc_x=px,
            loc_y=py,
            loc_z=CENTER_FLOOR_Z + (PCB_STAND_H / 2.0) + 0.5,
            vertices=14,
        )
        boolean_diff(base_obj, phole)

# Dudukan penahan HLK-PM01 di zona atas (34 x 20.2 x 15 mm, Y = +30.5 mm)
for hx in [-18.2, 18.2]:
    rib = add_box(
        f"HLK_Stop_{hx}",
        1.8,
        16.0,
        10.0,
        hx,
        30.5,
        FLOOR_T + 5.0,
        material=mat_white_body,
    )
    boolean_union(base_obj, rib)

# Lubang terminal masuk kabel AC (L, N) & soket CT Clamp di dinding BAWAH (Y = -BODY_H/2)
# Persis tata letak terminal MCB agar kabel langsung masuk rapi dari bawah!
for tx, rad in [(-11.0, 2.8), (-1.0, 2.8)]:  # L & N 220V
    ac_port = add_cylinder(
        f"AC_Wire_Port_{tx}",
        radius=rad,
        depth=WALL_T * 4.0,
        loc_x=tx,
        loc_y=-BODY_H / 2.0,
        loc_z=12.5,
        rot_x=math.radians(90.0),
        vertices=20,
    )
    boolean_diff(base_obj, ac_port)

# Lubang obeng pengencang baut terminal AC dari sisi muka bahu bawah (Z = BASE_D) -> dibuat di Lid & alur Base
# Soket plug-in CT Clamp (kanan bawah: X = +12.5 mm, Y = -BODY_H/2)
ct_port = add_rounded_box(
    "CT_Socket_Window",
    9.5,
    WALL_T * 4.0,
    7.5,
    radius=1.2,
    loc_x=12.5,
    loc_y=-BODY_H / 2.0,
    loc_z=12.5,
    segments=3,
)
boolean_diff(base_obj, ct_port)

# Kisi ventilasi pasif di dinding ATAS (Y = +BODY_H/2) dekat HLK-PM01
for vx in [-12.0, -6.0, 0.0, 6.0, 12.0]:
    top_vent = add_rounded_box(
        f"Top_Vent_{vx}",
        2.4,
        WALL_T * 4.0,
        8.5,
        radius=1.0,
        loc_x=vx,
        loc_y=BODY_H / 2.0,
        loc_z=15.0,
        segments=3,
    )
    boolean_diff(base_obj, top_vent)

# Jendela port USB-C servis (untuk flashing darurat) di dinding kanan Base (X = +BODY_W/2)
usbc_cut = add_rounded_box(
    "Service_USBC_Window",
    WALL_T * 4.0,
    10.5,
    5.0,
    radius=1.4,
    loc_x=BODY_W / 2.0,
    loc_y=6.0,
    loc_z=23.5,
    segments=3,
)
boolean_diff(base_obj, usbc_cut)

# ==========================================
# 2. DIN RAIL SNAP CLIP (Terpisah / Click-On)
# ==========================================
print("Mendesain DIN Rail Snap Clip v3.0...")
clip_z0 = 0.0
din_clip = add_rounded_box(
    "V3_DIN_Rail_Clip",
    16.0,
    24.0,
    3.2,
    radius=1.0,
    loc_x=0.0,
    loc_y=-(DIN_RAIL_W / 2.0) - 6.0,
    loc_z=1.6,
    segments=3,
    material=mat_slate_clip,
)
clip_wing = add_box(
    "DIN_Clip_T_Wing",
    19.6,
    14.0,
    1.2,
    0.0,
    -(DIN_RAIL_W / 2.0) - 5.0,
    2.6,
    material=mat_slate_clip,
)
boolean_union(din_clip, clip_wing)
clip_nose = add_box(
    "DIN_Clip_Catch",
    15.8,
    3.2,
    2.2,
    0.0,
    -(DIN_RAIL_W / 2.0) + 0.8,
    1.1,
    material=mat_slate_clip,
)
boolean_union(din_clip, clip_nose)
clip_pull_hole = add_box(
    "DIN_Clip_Pull_Slot",
    6.0,
    3.5,
    4.0,
    0.0,
    -(DIN_RAIL_W / 2.0) - 15.0,
    1.6,
)
boolean_diff(din_clip, clip_pull_hole)

# ==========================================
# 3. ENCLOSURE TOP LID v3.0 (Stepped DIN 45mm + Bezel Layar TFT IPS 1.3")
# ==========================================
print("Mendesain VoltKu Top Lid Stepped MCB v3.0...")

# Exploded preview: 10 mm di atas Base
LID_Z_OFFSET = BASE_D + 10.0

# 3a. Plat Bahu Bawah-Atas (Flange) 54 x 88 x 4 mm
lid_flange = add_rounded_box(
    "V3_DIN_Top_Lid",
    BODY_W,
    BODY_H,
    FLANGE_D,
    radius=CORNER_R,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=LID_Z_OFFSET + (FLANGE_D / 2.0),
    chamfer_top=0.6,
    segments=4,
    material=mat_white_body,
)

# 3b. Menara Muka Standar DIN 45mm (54 x 45 x 12 mm) menyambung di atas Flange
nose_total_z = FLANGE_D + NOSE_D
lid_nose = add_rounded_box(
    "Lid_Stepped_Nose",
    BODY_W,
    NOSE_H,
    NOSE_D + 1.0,
    radius=2.2,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=LID_Z_OFFSET + FLANGE_D + (NOSE_D / 2.0) - 0.5,
    chamfer_top=1.0,
    segments=4,
    material=mat_white_body,
)
boolean_union(lid_flange, lid_nose)
lid_obj = lid_flange

# Keruk bagian dalam Lid agar lega untuk layar TFT 1.3" & header ESP32-C3
lid_cav = add_rounded_box(
    "Lid_Inner_Cavity",
    inner_w - 1.0,
    NOSE_H - 4.4,
    NOSE_D + 1.5,
    radius=1.2,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=LID_Z_OFFSET + ((NOSE_D + 1.5) / 2.0) - 0.5,
    segments=4,
)
boolean_diff(lid_obj, lid_cav)

# Bibir pengunci (interlocking lip) di bawah flange agar menutup presisi ke Base
lip_outer = add_rounded_box(
    "Lid_Lip_Outer",
    inner_w - 0.6,
    inner_h - 0.6,
    2.2,
    radius=1.2,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=LID_Z_OFFSET - 1.0,
    segments=3,
    material=mat_white_body,
)
lip_inner = add_rounded_box(
    "Lid_Lip_Inner",
    inner_w - 3.4,
    inner_h - 3.4,
    3.6,
    radius=1.0,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=LID_Z_OFFSET - 1.0,
    segments=3,
)
boolean_diff(lip_outer, lip_inner)
boolean_union(lid_obj, lip_outer)

# 4 Lubang Baut M3 Countersunk di bahu luar tutup (pas mengikat Base dengan M3 x 16mm / 20mm)
for cx, cy in [
    (-CORNER_X, -CORNER_Y),
    (-CORNER_X, CORNER_Y),
    (CORNER_X, -CORNER_Y),
    (CORNER_X, CORNER_Y),
]:
    bolt_thru = add_cylinder(
        "Lid_Bolt_Hole",
        radius=1.65,
        depth=FLANGE_D + 4.0,
        loc_x=cx,
        loc_y=cy,
        loc_z=LID_Z_OFFSET + (FLANGE_D / 2.0),
        vertices=18,
    )
    boolean_diff(lid_obj, bolt_thru)
    bolt_csink = add_cone(
        "Lid_Bolt_Csink",
        r1=1.65,
        r2=3.1,
        depth=2.0,
        loc_x=cx,
        loc_y=cy,
        loc_z=LID_Z_OFFSET + FLANGE_D - 0.9,
        vertices=20,
    )
    boolean_diff(lid_obj, bolt_csink)

# 2 Lubang Akses Obeng untuk terminal sekrup AC (L, N) dari atas bahu bawah!
for tx in [-11.0, -1.0]:
    screw_access = add_cylinder(
        f"Terminal_Screw_Access_{tx}",
        radius=2.6,
        depth=FLANGE_D + 4.0,
        loc_x=tx,
        loc_y=-35.0,
        loc_z=LID_Z_OFFSET + (FLANGE_D / 2.0),
        vertices=18,
    )
    boolean_diff(lid_obj, screw_access)

# Ceruk Bezel Gelap Depan di muka Nose (Z_front = LID_Z_OFFSET + nose_total_z)
lid_front_z = LID_Z_OFFSET + nose_total_z
bezel_pocket = add_rounded_box(
    "Front_Bezel_Recess",
    48.0,
    38.0,
    1.6,
    radius=2.4,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=lid_front_z,
    segments=4,
)
boolean_diff(lid_obj, bezel_pocket)

# Jendela Layar TFT IPS 1.3" (24.0 x 24.0 mm) di kiri/tengah bezel (X = -7.0, Y = 0.0)
IPS_X = -7.0
IPS_Y = 0.0
ips_window = add_rounded_box(
    "TFT_IPS_Window",
    24.4,
    24.4,
    8.0,
    radius=1.2,
    loc_x=IPS_X,
    loc_y=IPS_Y,
    loc_z=lid_front_z - 2.0,
    segments=4,
)
boolean_diff(lid_obj, ips_window)

# Lubang Tombol Taktil PAIR / HALAMAN di kanan bezel (X = +16.0, Y = -9.5)
btn_hole = add_cylinder(
    "Pairing_Btn_Hole",
    radius=2.6,
    depth=8.0,
    loc_x=16.0,
    loc_y=-9.5,
    loc_z=lid_front_z - 2.0,
    vertices=20,
)
boolean_diff(lid_obj, btn_hole)

# 2 Lubang LED Indikator kecil di kanan bezel (PWR, WIFI)
for led_y in [-1.0, 4.5]:
    led_h = add_cylinder(
        f"Front_LED_Hole_{led_y}",
        radius=1.1,
        depth=8.0,
        loc_x=16.0,
        loc_y=led_y,
        loc_z=lid_front_z - 2.0,
        vertices=16,
    )
    boolean_diff(lid_obj, led_h)

# Tambahkan material aksen pada Lid
for m in (mat_bezel_dark, mat_navy, mat_blue, mat_amber):
    lid_obj.data.materials.append(m)

# Lapisan Bezel Dekoratif Gelap (dicetak multi-warna / tempel stiker panel) + Logo V-Crest VoltKu di pojok kanan atas
bezel_plate = add_rounded_box(
    "Front_Bezel_Plate",
    47.4,
    37.4,
    0.7,
    radius=2.1,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=lid_front_z - 0.5,
    segments=4,
    material=mat_bezel_dark,
)
# Lubangi bezel plate tepat di posisi IPS, tombol, & LED
for cutter_def in [
    ("bz_ips", "box", 24.4, 24.4, IPS_X, IPS_Y),
    ("bz_btn", "cyl", 2.6, 0.0, 16.0, -9.5),
    ("bz_l1", "cyl", 1.1, 0.0, 16.0, -1.0),
    ("bz_l2", "cyl", 1.1, 0.0, 16.0, 4.5),
]:
    cname, ckind, s1, s2, cx, cy = cutter_def
    if ckind == "box":
        c = add_rounded_box(cname, s1, s2, 4.0, 1.2, cx, cy, lid_front_z - 0.5)
    else:
        c = add_cylinder(cname, s1, 4.0, cx, cy, lid_front_z - 0.5)
    boolean_diff(bezel_plate, c)
boolean_union(lid_obj, bezel_plate)

# 4 Dudukan Baut Internal TFT IPS 1.3" (27.8 x 39.0 mm, pitch 23 x 34 mm) di dalam Top Lid
tft_stand_h = 3.2
for tx_off in [-11.5, 11.5]:
    for ty_off in [-17.0, 17.0]:
        tpost = add_cylinder(
            "TFT_Mount_Boss",
            radius=2.1,
            depth=tft_stand_h,
            loc_x=IPS_X + tx_off,
            loc_y=IPS_Y + ty_off,
            loc_z=lid_front_z - 2.0 - (tft_stand_h / 2.0),
            vertices=14,
            material=mat_white_body,
        )
        boolean_union(lid_obj, tpost)
        thole = add_cylinder(
            "TFT_Mount_Hole",
            radius=0.85,  # M2 self-tapping
            depth=tft_stand_h + 1.0,
            loc_x=IPS_X + tx_off,
            loc_y=IPS_Y + ty_off,
            loc_z=lid_front_z - 2.0 - (tft_stand_h / 2.0) - 0.5,
            vertices=12,
        )
        boolean_diff(lid_obj, thole)

# Emblem 3D V-Crest VoltKu tegak (huruf V terbuka ke atas + titik energi amber di atas tengah V)
emblem_z = lid_front_z - 0.12
v_left = add_rounded_box("V3_V_Left", 1.9, 6.4, 0.55, 0.5, 14.5, 12.2, emblem_z, segments=3, material=mat_navy)
v_left.rotation_euler = (0.0, 0.0, math.radians(24.0))
bpy.context.view_layer.objects.active = v_left
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

v_right = add_rounded_box("V3_V_Right", 1.9, 6.4, 0.55, 0.5, 17.5, 12.2, emblem_z, segments=3, material=mat_blue)
v_right.rotation_euler = (0.0, 0.0, math.radians(-24.0))
bpy.context.view_layer.objects.active = v_right
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

v_dot = add_cylinder("V3_Energy_Dot", 0.95, 0.55, 16.0, 14.4, emblem_z, vertices=18, material=mat_amber)
for vp in (v_left, v_right, v_dot):
    boolean_union(lid_obj, vp)

# ==========================================
# 4. KOMPONEN ELEKTRONIK REFERENSI (Fit Check & Showcase Render)
# ==========================================
print("Menambahkan Model Referensi Elektronik Internal & Layar IPS...")

# 4a. HLK-PM01 Isolated 5V PSU (34 x 20.2 x 15 mm) di zona atas
hlk_box = add_rounded_box(
    "Ref_HLK_PM01",
    34.0,
    20.0,
    15.0,
    radius=1.0,
    loc_x=0.0,
    loc_y=30.5,
    loc_z=FLOOR_T + 7.5,
    segments=3,
    material=mat_psu_black,
)

# 4b. Terminal Block AC 220V (2-pin L/N) & CT Connector di zona bawah
ac_term = add_box("Ref_AC_Terminal", 18.0, 11.0, 11.5, -6.0, -34.5, FLOOR_T + 6.0, material=mat_term_green)
s_l = add_cylinder("Ref_Screw_L", 2.1, 2.0, -11.0, -34.5, FLOOR_T + 11.8, vertices=16, material=mat_brass)
s_n = add_cylinder("Ref_Screw_N", 2.1, 2.0, -1.0, -34.5, FLOOR_T + 11.8, vertices=16, material=mat_brass)
ct_conn = add_box("Ref_CT_Connector", 8.5, 10.0, 7.0, 12.5, -35.5, FLOOR_T + 4.5, material=mat_slate_clip)

# 4c. VoltKu Custom Carrier PCB (45 x 34 x 1.6 mm) + ESP32-C3 + BL0942
pcb_z = CENTER_FLOOR_Z + PCB_STAND_H + 0.8
main_pcb = add_box("Ref_Main_Carrier_PCB", 45.0, 34.0, 1.6, 0.0, 0.0, pcb_z, material=mat_pcb_navy)
esp_c3 = add_box("Ref_ESP32_C3_SuperMini", 18.0, 22.5, 3.8, 12.5, 4.0, pcb_z + 2.7, material=mat_alu)
bl0942_ic = add_box("Ref_BL0942_IC", 5.0, 4.0, 1.2, -11.0, -6.0, pcb_z + 1.4, material=mat_psu_black)
tact_btn = add_cylinder("Ref_Pairing_Button", 2.3, 13.0, 16.0, -9.5, lid_front_z - 6.8, vertices=18, material=mat_blue)

# 4d. Modul Layar TFT IPS 1.3" + Simulasi Tampilan UI Modern di Layar (Hanya di Electronics_Reference)
tft_pcb = add_box("Ref_TFT_IPS_PCB", 27.8, 39.0, 1.6, IPS_X, IPS_Y, lid_front_z - 5.2, material=mat_pcb_navy)
ips_panel = add_box("Ref_TFT_Glass", 24.0, 24.0, 0.5, IPS_X, IPS_Y, lid_front_z - 1.1, material=mat_ips_bg)

# Elemen UI menyala di layar TFT (Power, Biaya Rupiah, Tegangan/Arus, Wi-Fi bar)
ui_pwr_bar = add_rounded_box("UI_Power_Main", 16.0, 3.6, 0.2, 0.4, IPS_X - 1.0, IPS_Y + 6.5, lid_front_z - 0.8, segments=2, material=mat_ui_amber)
ui_rp_bar = add_rounded_box("UI_Rupiah_Row", 14.0, 2.2, 0.2, 0.3, IPS_X - 2.0, IPS_Y + 1.8, lid_front_z - 0.8, segments=2, material=mat_ui_green)
ui_v_bar = add_rounded_box("UI_Volt_Box", 8.5, 2.0, 0.2, 0.3, IPS_X - 5.0, IPS_Y - 3.2, lid_front_z - 0.8, segments=2, material=mat_ui_cyan)
ui_a_bar = add_rounded_box("UI_Amp_Box", 8.5, 2.0, 0.2, 0.3, IPS_X + 5.0, IPS_Y - 3.2, lid_front_z - 0.8, segments=2, material=mat_ui_cyan)
ui_status_pill = add_rounded_box("UI_Status_Pill", 17.5, 2.4, 0.2, 0.5, IPS_X, IPS_Y - 7.8, lid_front_z - 0.8, segments=2, material=mat_ui_green)

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
    (tft_pcb, "TFT 1.3 IPS Module"),
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
    tact_btn, tft_pcb, ips_panel, ui_pwr_bar, ui_rp_bar, ui_v_bar, ui_a_bar, ui_status_pill,
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
# 7. STUDIO RENDER PRODUCT SHOWCASE v3.0
# ==========================================
print("Menyiapkan Studio Render VoltKu DIN-Rail v3.0...")

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
    bg_node.inputs[0].default_value = (0.09, 0.12, 0.18, 1.0)
    bg_node.inputs[1].default_value = 0.60

bpy.ops.object.light_add(type="SUN", location=(110.0, -130.0, 200.0))
sun_key = bpy.context.active_object
sun_key.name = "Studio_Sun_Key"
sun_key.data.energy = 2.8
sun_key.data.angle = math.radians(10.0)
sun_key.data.color = (1.0, 0.99, 0.96)
sun_key.rotation_euler = (math.radians(38.0), math.radians(14.0), math.radians(36.0))
move_to_collection(sun_key, "Studio_Setup")

bpy.ops.object.light_add(type="AREA", location=(-130.0, 90.0, 120.0))
fill_light = bpy.context.active_object
fill_light.name = "Studio_Fill"
fill_light.data.energy = 11.0
fill_light.data.size = 150.0
fill_light.data.color = (0.78, 0.89, 1.0)
fill_light.rotation_euler = (Vector((0.0, 0.0, 28.0)) - fill_light.location).to_track_quat("-Z", "Y").to_euler()
move_to_collection(fill_light, "Studio_Setup")

bpy.ops.object.light_add(type="AREA", location=(15.0, 140.0, 140.0))
rim_light = bpy.context.active_object
rim_light.name = "Studio_Rim"
rim_light.data.energy = 14.0
rim_light.data.size = 140.0
rim_light.data.color = (0.94, 0.98, 1.0)
rim_light.rotation_euler = (Vector((0.0, 0.0, 32.0)) - rim_light.location).to_track_quat("-Z", "Y").to_euler()
move_to_collection(rim_light, "Studio_Setup")

bpy.ops.object.camera_add(location=(92.0, -108.0, 122.0))
cam = bpy.context.active_object
cam.name = "Main_Camera"
cam.rotation_euler = (Vector((0.0, -2.0, 34.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
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
print(f"-> Render preview v3.0 tersimpan di: {preview_v3_path}")

blend_v3_path = os.path.join(CURRENT_DIR, "energy_monitor_v3.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_v3_path)
print(f"-> File Blender v3.0 tersimpan di: {blend_v3_path}")

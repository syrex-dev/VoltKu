"""
Script Generator 3D Casing v2.0 - VoltKu Smart Energy Monitor (ESP32 + PZEM-004T v3.0)
Dibuat otomatis untuk Blender 5.3+.

Peningkatan Desain v2.0:
1. Bodi ergonomis ber-radius (rounded corners + chamfer atas/bawah) ala meteran DIN/smart-home modern.
2. Rotasi PZEM-004T 90 derajat agar muat lega tanpa tabrakan dengan dinding maupun ruang jumper/divider.
3. Jalur kabel model U-slot terbuka di atas (drop-in wiring): pasang kabel AC/CT dulu, tinggal jatuhkan
   masuk lalu tutup penutupnya tanpa repot memasukkan kabel lewat lubang sempit.
4. Kuping dinding model keyhole-slot (mudah digantung/dilepas) + kanal rel DIN 35mm di belakang.
5. Tutup atas dengan frame aksen, logo 3D V-crest VoltKu, 3 lubang LED indikator chamfered, kisi
   ventilasi dual-kolom modern, dan kantong baut M3 rata permukaan (countersunk).
6. Tetap 100% printable tanpa support (Base rata di Z=0, Lid telungkup rata di Z=0).
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


def create_material(name, color_rgba, roughness=0.35, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color_rgba
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
    return mat


mat_base = create_material("Mat_VoltKu_Base", (0.14, 0.18, 0.25, 1.0), roughness=0.42)
mat_lid = create_material("Mat_VoltKu_Lid", (0.94, 0.96, 0.99, 1.0), roughness=0.28)
mat_navy = create_material("Mat_VoltKu_Navy", (0.06, 0.14, 0.30, 1.0), roughness=0.25)
mat_blue = create_material("Mat_VoltKu_Blue", (0.08, 0.46, 0.98, 1.0), roughness=0.22)
mat_amber = create_material("Mat_VoltKu_Amber", (0.96, 0.62, 0.04, 1.0), roughness=0.20)
mat_esp32 = create_material("Mat_ESP32_PCB", (0.07, 0.32, 0.18, 1.0), roughness=0.38)
mat_pzem = create_material("Mat_PZEM_PCB", (0.05, 0.20, 0.48, 1.0), roughness=0.35)
mat_dark_part = create_material("Mat_Dark_Component", (0.06, 0.08, 0.11, 1.0), roughness=0.45)
mat_brass = create_material("Mat_Brass_Metal", (0.85, 0.68, 0.20, 1.0), roughness=0.22, metallic=0.85)
mat_alu = create_material("Mat_Aluminum_Can", (0.76, 0.80, 0.86, 1.0), roughness=0.24, metallic=0.85)
mat_studio = create_material("Mat_Studio_Floor", (0.09, 0.11, 0.16, 1.0), roughness=0.75)


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
    segments=6,
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
    vertices=28,
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


def add_cone(name, r1, r2, depth, loc_x, loc_y, loc_z, vertices=28, material=None):
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


def add_u_notch_cutter(name, axis, width, bottom_z, top_z, wall_pos, offset_along_wall, depth):
    """Pemotong celah kabel U-slot terbuka di bagian atas dinding base (drop-in wiring)."""
    rect_h = top_z - bottom_z
    rect_center_z = bottom_z + (rect_h / 2.0)
    r = width / 2.0
    if axis == "X":
        c_box = add_box(
            f"{name}_Rect",
            depth,
            width,
            rect_h,
            wall_pos,
            offset_along_wall,
            rect_center_z,
        )
        c_cyl = add_cylinder(
            f"{name}_Cyl",
            radius=r,
            depth=depth,
            loc_x=wall_pos,
            loc_y=offset_along_wall,
            loc_z=bottom_z,
            rot_y=math.radians(90),
            vertices=24,
        )
    else:
        c_box = add_box(
            f"{name}_Rect",
            width,
            depth,
            rect_h,
            offset_along_wall,
            wall_pos,
            rect_center_z,
        )
        c_cyl = add_cylinder(
            f"{name}_Cyl",
            radius=r,
            depth=depth,
            loc_x=offset_along_wall,
            loc_y=wall_pos,
            loc_z=bottom_z,
            rot_x=math.radians(90),
            vertices=24,
        )
    boolean_union(c_box, c_cyl)
    return c_box


# ==========================================
# DIMENSI UTAMA CASING v2.0 (mm)
# ==========================================
OUTER_L = 128.0
OUTER_W = 96.0
CORNER_R = 8.0
WALL_T = 2.6
FLOOR_T = 2.6
BASE_H = 29.0
LID_H = 14.0
LID_TOP_T = 2.6

inner_l = OUTER_L - (2.0 * WALL_T)
inner_w = OUTER_W - (2.0 * WALL_T)
inner_r = max(2.0, CORNER_R - WALL_T)

# ==========================================
# 1. ENCLOSURE BOTTOM BASE (Wadah Bawah)
# ==========================================
print("Mendesain VoltKu Base v2.0...")

base_obj = add_rounded_box(
    "Enclosure_Bottom_Base",
    OUTER_L,
    OUTER_W,
    BASE_H,
    radius=CORNER_R,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=BASE_H / 2.0,
    chamfer_bottom=1.2,
    segments=6,
    material=mat_base,
)

# Rongga dalam mengikuti bentuk rounded corner
inner_h = BASE_H - FLOOR_T + 3.0
inner_cutter = add_rounded_box(
    "Base_Inner_Cutter",
    inner_l,
    inner_w,
    inner_h,
    radius=inner_r,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=FLOOR_T + (inner_h / 2.0),
    segments=6,
)
boolean_diff(base_obj, inner_cutter)

# Aksen alur grip horizontal pada sisi kiri & kanan luar
for side_x in [-OUTER_L / 2.0, OUTER_L / 2.0]:
    for gz in [9.5, 14.5, 19.5]:
        rib = add_rounded_box(
            f"Side_Grip_{side_x}_{gz}",
            1.4,
            44.0,
            1.6,
            radius=0.5,
            loc_x=side_x,
            loc_y=0.0,
            loc_z=gz,
            segments=3,
        )
        boolean_diff(base_obj, rib)

# Dinding Sekat Isolasi AC vs DC di X = -3.0 mm (dengan celah U terbuka di atas untuk kabel UART)
BARRIER_X = -3.0
barrier_t = 2.4
barrier_h = 23.0
barrier_obj = add_box(
    "Safety_Barrier",
    barrier_t,
    inner_w + 0.4,
    barrier_h,
    BARRIER_X,
    0.0,
    FLOOR_T + (barrier_h / 2.0),
    material=mat_base,
)
# Celah kabel UART terbuka di atas pada Y = 0.0 (sejajar tengah ESP32)
uart_u = add_u_notch_cutter(
    "UART_Notch",
    axis="X",
    width=18.0,
    bottom_z=FLOOR_T + 11.0,
    top_z=BASE_H + 2.0,
    wall_pos=BARRIER_X,
    offset_along_wall=0.0,
    depth=barrier_t + 3.0,
)
boolean_diff(barrier_obj, uart_u)
boolean_union(base_obj, barrier_obj)

# 4 Corner Screw Bosses dengan penguat rusuk ke dinding
corner_x = (OUTER_L / 2.0) - 6.8
corner_y = (OUTER_W / 2.0) - 6.8
boss_h = BASE_H - FLOOR_T

for cx, cy in [
    (-corner_x, -corner_y),
    (-corner_x, corner_y),
    (corner_x, -corner_y),
    (corner_x, corner_y),
]:
    boss = add_cylinder(
        "Corner_Boss",
        radius=4.3,
        depth=boss_h,
        loc_x=cx,
        loc_y=cy,
        loc_z=FLOOR_T + (boss_h / 2.0),
        vertices=24,
        material=mat_base,
    )
    boolean_union(base_obj, boss)
    hole = add_cylinder(
        "Corner_Screw_Hole",
        radius=1.35,
        depth=boss_h + 2.0,
        loc_x=cx,
        loc_y=cy,
        loc_z=FLOOR_T + (boss_h / 2.0) + 1.0,
        vertices=18,
    )
    boolean_diff(base_obj, hole)

# Posisi Komponen Internal (Lega, nol tabrakan):
# 1) PZEM-004T v3.0 (31 x 72 mm) dipasang VERTIKAL di ruang kiri (X = -31.0, Y = 0.0)
PZEM_X = -31.0
PZEM_Y = 0.0
PZEM_STAND_H = 5.5
for px in [-11.5, 11.5]:  # pitch X = 23 mm
    for py in [-33.0, 33.0]:  # pitch Y = 66 mm
        pst = add_cylinder(
            "PZEM_Standoff",
            radius=3.1,
            depth=PZEM_STAND_H,
            loc_x=PZEM_X + px,
            loc_y=PZEM_Y + py,
            loc_z=FLOOR_T + (PZEM_STAND_H / 2.0),
            vertices=20,
            material=mat_base,
        )
        boolean_union(base_obj, pst)
        phole = add_cylinder(
            "PZEM_Hole",
            radius=1.15,
            depth=PZEM_STAND_H + 2.0,
            loc_x=PZEM_X + px,
            loc_y=PZEM_Y + py,
            loc_z=FLOOR_T + (PZEM_STAND_H / 2.0) + 1.0,
            vertices=14,
        )
        boolean_diff(base_obj, phole)

# 2) ESP32 DevKit V1 (51.5 x 28.5 mm) simetris di ruang kanan (X = +31.0, Y = 0.0)
ESP_X = 31.0
ESP_Y = 0.0
ESP_STAND_H = 6.0
for sx in [-24.0, 24.0]:  # pitch X = 48 mm
    for sy in [-11.5, 11.5]:  # pitch Y = 23 mm
        est = add_cylinder(
            "ESP_Standoff",
            radius=3.0,
            depth=ESP_STAND_H,
            loc_x=ESP_X + sx,
            loc_y=ESP_Y + sy,
            loc_z=FLOOR_T + (ESP_STAND_H / 2.0),
            vertices=20,
            material=mat_base,
        )
        boolean_union(base_obj, est)
        ehole = add_cylinder(
            "ESP_Hole",
            radius=1.1,
            depth=ESP_STAND_H + 2.0,
            loc_x=ESP_X + sx,
            loc_y=ESP_Y + sy,
            loc_z=FLOOR_T + (ESP_STAND_H / 2.0) + 1.0,
            vertices=14,
        )
        boolean_diff(base_obj, ehole)

# Jendela Port USB ESP32 yang lega (dinding kanan X = +OUTER_L/2)
usb_cut = add_rounded_box(
    "USB_Port_Window",
    WALL_T * 3.5,
    15.0,
    10.0,
    radius=1.8,
    loc_x=OUTER_L / 2.0,
    loc_y=ESP_Y,
    loc_z=FLOOR_T + ESP_STAND_H + 4.8,
    segments=4,
)
boolean_diff(base_obj, usb_cut)

# Jendela U-Slot Kabel AC 220V (Dinding Kiri: drop-in dari atas, sangat mudah dipasang)
for ac_y in [-18.0, 18.0]:
    ac_notch = add_u_notch_cutter(
        f"AC_Notch_{ac_y}",
        axis="X",
        width=7.5,
        bottom_z=15.0,
        top_z=BASE_H + 3.0,
        wall_pos=-OUTER_L / 2.0,
        offset_along_wall=ac_y,
        depth=WALL_T * 3.5,
    )
    boolean_diff(base_obj, ac_notch)

# Jendela U-Slot Kabel CT Clamp (Dinding Belakang Y = +OUTER_W/2 di zona PZEM)
ct_notch = add_u_notch_cutter(
    "CT_Clamp_Notch",
    axis="Y",
    width=8.5,
    bottom_z=15.0,
    top_z=BASE_H + 3.0,
    wall_pos=OUTER_W / 2.0,
    offset_along_wall=PZEM_X,
    depth=WALL_T * 3.5,
)
boolean_diff(base_obj, ct_notch)

# Kuping Pemasangan Dinding Model Keyhole-Slot dengan Sudut Membulat (Kiri & Kanan)
EAR_EXT = 15.0
EAR_W = 24.0
EAR_T = 4.2
for dir_x in [-1.0, 1.0]:
    ex_center = dir_x * ((OUTER_L / 2.0) + (EAR_EXT / 2.0) - 2.0)
    ear = add_rounded_box(
        f"Mounting_Ear_{dir_x}",
        EAR_EXT + 4.0,
        EAR_W,
        EAR_T,
        radius=5.0,
        loc_x=ex_center,
        loc_y=0.0,
        loc_z=EAR_T / 2.0,
        chamfer_top=0.7,
        segments=5,
        material=mat_base,
    )
    boolean_union(base_obj, ear)

    # Lubang Keyhole: bagian bawah besar (D=7.6mm) + slot atas (lebar 4.2mm)
    slot_x = dir_x * ((OUTER_L / 2.0) + 7.5)
    kh_big = add_cylinder(
        "Keyhole_Big",
        radius=3.8,
        depth=EAR_T + 3.0,
        loc_x=slot_x,
        loc_y=-3.2,
        loc_z=EAR_T / 2.0,
        vertices=24,
    )
    kh_small = add_cylinder(
        "Keyhole_Small",
        radius=2.1,
        depth=EAR_T + 3.0,
        loc_x=slot_x,
        loc_y=3.5,
        loc_z=EAR_T / 2.0,
        vertices=20,
    )
    kh_bar = add_box(
        "Keyhole_Bar",
        4.2,
        6.7,
        EAR_T + 3.0,
        slot_x,
        0.15,
        EAR_T / 2.0,
    )
    boolean_union(kh_big, kh_small)
    boolean_union(kh_big, kh_bar)
    boolean_diff(base_obj, kh_big)

# Kanal DIN-Rail 35mm di Bagian Dasar Bawah (EN 50022) + Slot Kabel Ties
din_channel = add_box(
    "DIN_Rail_Channel",
    OUTER_L + 40.0,
    35.6,
    1.6,
    0.0,
    0.0,
    0.8,
)
boolean_diff(base_obj, din_channel)

# ==========================================
# 2. ENCLOSURE TOP LID (Tutup Atas Estetik)
# ==========================================
print("Mendesain VoltKu Top Lid v2.0...")

# Posisi meledak (exploded view) rapi 16 mm di atas Base untuk preview/assembly
LID_Z_OFFSET = BASE_H + 16.0

lid_obj = add_rounded_box(
    "Enclosure_Top_Lid",
    OUTER_L,
    OUTER_W,
    LID_H,
    radius=CORNER_R,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=LID_Z_OFFSET + (LID_H / 2.0),
    chamfer_top=1.8,
    segments=6,
    material=mat_lid,
)

# Rongga dalam tutup
lid_inner_h = LID_H - LID_TOP_T + 2.0
lid_cutter = add_rounded_box(
    "Lid_Inner_Cutter",
    inner_l,
    inner_w,
    lid_inner_h,
    radius=inner_r,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=LID_Z_OFFSET + (lid_inner_h / 2.0) - 1.0,
    segments=6,
)
boolean_diff(lid_obj, lid_cutter)

# Bibir Pengunci (Interlocking Lip) agar menutup presisi ke dinding Base
lip_h = 2.6
lip_t = 1.4
lip_ol = inner_l - 0.5
lip_ow = inner_w - 0.5
lip_ir = max(1.5, inner_r - 0.25)

lip_outer = add_rounded_box(
    "Lid_Lip_Outer",
    lip_ol,
    lip_ow,
    lip_h,
    radius=lip_ir,
    loc_x=0.0,
    loc_y=0.0,
    loc_z=LID_Z_OFFSET - (lip_h / 2.0) + 0.1,
    segments=6,
    material=mat_lid,
)
lip_inner = add_rounded_box(
    "Lid_Lip_Inner",
    lip_ol - (2.0 * lip_t),
    lip_ow - (2.0 * lip_t),
    lip_h + 2.0,
    radius=max(1.0, lip_ir - lip_t),
    loc_x=0.0,
    loc_y=0.0,
    loc_z=LID_Z_OFFSET - (lip_h / 2.0) + 0.1,
    segments=6,
)
boolean_diff(lip_outer, lip_inner)
boolean_union(lid_obj, lip_outer)

# 4 Lubang Baut Countersunk M3 di Sudut Tutup
lid_top_z = LID_Z_OFFSET + LID_H
for cx, cy in [
    (-corner_x, -corner_y),
    (-corner_x, corner_y),
    (corner_x, -corner_y),
    (corner_x, corner_y),
]:
    bolt_thru = add_cylinder(
        "Lid_Bolt_Hole",
        radius=1.7,
        depth=LID_H + 6.0,
        loc_x=cx,
        loc_y=cy,
        loc_z=LID_Z_OFFSET + (LID_H / 2.0),
        vertices=22,
    )
    boolean_diff(lid_obj, bolt_thru)
    bolt_csink = add_cone(
        "Lid_Countersink",
        r1=1.7,
        r2=3.4,
        depth=2.4,
        loc_x=cx,
        loc_y=cy,
        loc_z=lid_top_z - 1.1,
        vertices=24,
    )
    boolean_diff(lid_obj, bolt_csink)

# Kisi Ventilasi Udara Dual-Kolom Modern di Atas Zona PZEM/AC (X = -46 .. -12)
for vx in [-39.0, -19.0]:
    for i in range(-4, 5):
        vy = i * 5.6
        vent = add_rounded_box(
            f"Vent_{vx}_{i}",
            15.0,
            2.4,
            LID_TOP_T + 4.0,
            radius=1.1,
            loc_x=vx,
            loc_y=vy,
            loc_z=lid_top_z - (LID_TOP_T / 2.0),
            segments=4,
        )
        boolean_diff(lid_obj, vent)

# Recess / Ceruk Dekoratif Panel Status di Zona ESP32 (kedalaman 0.8mm — tetap printable rata!)
badge_recess = add_rounded_box(
    "Badge_Recess",
    46.0,
    54.0,
    1.6,
    radius=5.0,
    loc_x=29.0,
    loc_y=0.0,
    loc_z=lid_top_z,
    segments=5,
)
boolean_diff(lid_obj, badge_recess)

# 3 Lubang Indikator LED Chamfered (PWR, WIFI, DATA) simetris di sisi kanan panel status
for name, ly in [("PWR", -11.0), ("WIFI", 0.0), ("DATA", 11.0)]:
    led_hole = add_cylinder(
        f"LED_{name}",
        radius=1.6,
        depth=LID_TOP_T + 5.0,
        loc_x=43.5,
        loc_y=ly,
        loc_z=lid_top_z - (LID_TOP_T / 2.0),
        vertices=24,
    )
    boolean_diff(lid_obj, led_hole)
    led_chamfer = add_cone(
        f"LED_Chamfer_{name}",
        r1=1.6,
        r2=2.8,
        depth=1.6,
        loc_x=43.5,
        loc_y=ly,
        loc_z=lid_top_z - 0.8,
        vertices=24,
    )
    boolean_diff(lid_obj, led_chamfer)

# Tambahkan material aksen ke Lid agar warna emblem V-Crest tampil di Blender render
for accent_mat in (mat_navy, mat_blue, mat_amber):
    lid_obj.data.materials.append(accent_mat)

# Logo V-Crest VoltKu Timbul Simetris di ceruk status (puncak emblem di lid_top_z - 0.05mm)
# Membentuk huruf V menghadap ke depan (ujung lancip di X = +31.0, Y = 0.0)
emblem_z = lid_top_z - 0.42
v_left = add_rounded_box(
    "VoltKu_V_Left",
    17.5,
    4.4,
    0.75,
    radius=1.2,
    loc_x=23.5,
    loc_y=4.2,
    loc_z=emblem_z,
    segments=4,
    material=mat_navy,
)
v_left.rotation_euler = (0.0, 0.0, math.radians(-26.0))
bpy.context.view_layer.objects.active = v_left
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

v_right = add_rounded_box(
    "VoltKu_V_Right",
    17.5,
    4.4,
    0.75,
    radius=1.2,
    loc_x=23.5,
    loc_y=-4.2,
    loc_z=emblem_z,
    segments=4,
    material=mat_blue,
)
v_right.rotation_euler = (0.0, 0.0, math.radians(26.0))
bpy.context.view_layer.objects.active = v_right
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

v_dot = add_cylinder(
    "VoltKu_Energy_Dot",
    radius=2.1,
    depth=0.75,
    loc_x=17.5,
    loc_y=0.0,
    loc_z=emblem_z,
    vertices=24,
    material=mat_amber,
)

# Gabungkan V-Crest ke objek Lid supaya ikut tercetak solid di STL Top Lid
boolean_union(lid_obj, v_left)
boolean_union(lid_obj, v_right)
boolean_union(lid_obj, v_dot)

# ==========================================
# 3. KOMPONEN ELEKTRONIK REFERENSI (Fit-Check Akurat)
# ==========================================
print("Menambahkan Modul Elektronik Referensi...")

esp_z = FLOOR_T + ESP_STAND_H + 0.8
esp_board = add_box(
    "Dummy_ESP32_DevKit",
    51.5,
    28.5,
    1.6,
    ESP_X,
    ESP_Y,
    esp_z,
    material=mat_esp32,
)
esp_shield = add_box(
    "ESP32_Metal_Can",
    18.0,
    16.0,
    3.2,
    ESP_X - 11.0,
    ESP_Y,
    esp_z + 2.4,
    material=mat_alu,
)
esp_usb = add_box(
    "ESP32_USB_Connector",
    8.5,
    8.5,
    3.2,
    ESP_X + 22.0,
    ESP_Y,
    esp_z + 2.4,
    material=mat_brass,
)
# 3 Pin LED Status Dummy sejajar lubang LED di Lid
led_pwr = add_cylinder("LED_Glow_PWR", 1.3, 2.0, 43.5, -11.0, esp_z + 2.2, material=mat_amber)
led_wifi = add_cylinder("LED_Glow_WIFI", 1.3, 2.0, 43.5, 0.0, esp_z + 2.2, material=mat_blue)
led_data = add_cylinder("LED_Glow_DATA", 1.3, 2.0, 43.5, 11.0, esp_z + 2.2, material=mat_blue)

# PZEM-004T v3.0 (31 x 72 mm) vertikal di kiri
pzem_z = FLOOR_T + PZEM_STAND_H + 0.8
pzem_board = add_box(
    "Dummy_PZEM004T",
    31.0,
    72.0,
    1.6,
    PZEM_X,
    PZEM_Y,
    pzem_z,
    material=mat_pzem,
)
pzem_term_ac = add_box(
    "PZEM_AC_Terminal_4Pin",
    11.0,
    22.0,
    11.0,
    PZEM_X - 9.0,
    PZEM_Y - 19.0,
    pzem_z + 6.3,
    material=mat_dark_part,
)
pzem_coil = add_cylinder(
    "PZEM_Shunt_Transformer",
    radius=7.0,
    depth=11.0,
    loc_x=PZEM_X - 6.0,
    loc_y=PZEM_Y + 12.0,
    loc_z=pzem_z + 6.3,
    material=mat_dark_part,
)
pzem_uart = add_box(
    "PZEM_UART_Header",
    4.0,
    12.0,
    8.0,
    PZEM_X + 12.0,
    ESP_Y,
    pzem_z + 4.8,
    material=mat_dark_part,
)

# ==========================================
# 4. ORGANISASI KOLEKSI BLENDER
# ==========================================
def move_to_collection(obj, coll_name):
    coll = bpy.data.collections.get(coll_name)
    if not coll:
        coll = bpy.data.collections.new(coll_name)
        bpy.context.scene.collection.children.link(coll)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)


move_to_collection(base_obj, "Enclosure_Base")
move_to_collection(lid_obj, "Enclosure_Lid")
for dummy in [
    esp_board,
    esp_shield,
    esp_usb,
    led_pwr,
    led_wifi,
    led_data,
    pzem_board,
    pzem_term_ac,
    pzem_coil,
    pzem_uart,
]:
    move_to_collection(dummy, "Electronics_Reference")

# ==========================================
# 5. EKSPOR BERKAS STL SIAP CETAK
# ==========================================
print("Mengekspor STL Siap Cetak v2.0...")


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


base_stl_path = os.path.join(EXPORT_DIR, "enclosure_bottom_base.stl")
export_selected_stl([base_obj], base_stl_path, orient_lid_down=False)

lid_stl_path = os.path.join(EXPORT_DIR, "enclosure_top_lid.stl")
export_selected_stl([lid_obj], lid_stl_path, orient_lid_down=True)

assembly_stl_path = os.path.join(EXPORT_DIR, "enclosure_assembly_preview.stl")
export_selected_stl([base_obj, lid_obj], assembly_stl_path, orient_lid_down=False)

# ==========================================
# 6. STUDIO RENDER PREVIEW (High-Contrast Product Showcase)
# ==========================================
print("Menyiapkan Render Studio...")

bpy.ops.mesh.primitive_plane_add(size=1600.0, location=(0.0, 0.0, -0.5))
floor_plane = bpy.context.active_object
floor_plane.name = "Studio_Backdrop"
floor_plane.data.materials.append(mat_studio)
move_to_collection(floor_plane, "Studio_Setup")

world = bpy.data.worlds.new("VoltKu_Studio_World")
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs[0].default_value = (0.11, 0.14, 0.20, 1.0)
    bg_node.inputs[1].default_value = 0.55

# Pencahayaan Studio 3-Titik (skala energi disesuaikan jarak mm!)
bpy.ops.object.light_add(type="SUN", location=(120.0, -140.0, 220.0))
sun_key = bpy.context.active_object
sun_key.name = "Studio_Sun_Key"
sun_key.data.energy = 2.6
sun_key.data.angle = math.radians(12.0)
sun_key.data.color = (1.0, 0.99, 0.96)
sun_key.rotation_euler = (math.radians(40.0), math.radians(16.0), math.radians(38.0))
move_to_collection(sun_key, "Studio_Setup")

bpy.ops.object.light_add(type="AREA", location=(-150.0, 110.0, 140.0))
fill_light = bpy.context.active_object
fill_light.name = "Studio_Fill"
fill_light.data.energy = 12.0
fill_light.data.size = 180.0
fill_light.data.color = (0.76, 0.88, 1.0)
fill_dir = Vector((0.0, 0.0, 20.0)) - fill_light.location
fill_light.rotation_euler = fill_dir.to_track_quat("-Z", "Y").to_euler()
move_to_collection(fill_light, "Studio_Setup")

bpy.ops.object.light_add(type="AREA", location=(20.0, 170.0, 160.0))
rim_light = bpy.context.active_object
rim_light.name = "Studio_Rim"
rim_light.data.energy = 16.0
rim_light.data.size = 160.0
rim_light.data.color = (0.94, 0.98, 1.0)
rim_dir = Vector((0.0, 0.0, 30.0)) - rim_light.location
rim_light.rotation_euler = rim_dir.to_track_quat("-Z", "Y").to_euler()
move_to_collection(rim_light, "Studio_Setup")

# Kamera Isometrik Mengarah ke Pusat Assembly
bpy.ops.object.camera_add(location=(158.0, -168.0, 150.0))
cam = bpy.context.active_object
cam.name = "Main_Camera"
direction = Vector((0.0, 0.0, 26.0)) - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 40.0
scene.camera = cam
move_to_collection(cam, "Studio_Setup")

scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1440
scene.render.resolution_y = 900
scene.render.image_settings.file_format = "PNG"
preview_img_path = os.path.join(CURRENT_DIR, "render_preview.png")
scene.render.filepath = preview_img_path

bpy.ops.render.render(write_still=True)
print(f"-> Render preview tersimpan di: {preview_img_path}")

blend_file_path = os.path.join(CURRENT_DIR, "energy_monitor_case.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_file_path)
print(f"-> File Blender tersimpan di: {blend_file_path}")

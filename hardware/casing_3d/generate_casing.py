"""
Script Generator 3D Casing - Smart Energy Monitor (ESP32 + PZEM-004T)
Dibuat otomatis untuk Blender 5.3+.
Menghasilkan:
1. energy_monitor_case.blend (File proyek Blender siap edit/buka)
2. export/enclosure_bottom_base.stl (Komponen bawah untuk 3D printing)
3. export/enclosure_top_lid.stl (Komponen tutup atas untuk 3D printing)
4. export/enclosure_assembly_preview.stl (Full assembly casing + modul)
5. render_preview.png (Gambar visualisasi 3D casing)
"""

import bpy
import bmesh
import math
import os
from mathutils import Vector, Matrix

# Direktori output
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(CURRENT_DIR, "export")
os.makedirs(EXPORT_DIR, exist_ok=True)

# 1. Bersihkan Scene Default Blender
bpy.ops.wm.read_factory_settings(use_empty=True)

# Set Unit ke Milimeter
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 0.001  # 1 Blender Unit = 1 Meter, skala 0.001 = 1 mm
scene.unit_settings.length_unit = 'MILLIMETERS'

def create_material(name, color_rgba, roughness=0.35, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color_rgba
        bsdf.inputs['Roughness'].default_value = roughness
        if 'Metallic' in bsdf.inputs:
            bsdf.inputs['Metallic'].default_value = metallic
    return mat

mat_base = create_material("Mat_Enclosure_Base", (0.92, 0.93, 0.95, 1.0), roughness=0.3)
mat_lid = create_material("Mat_Enclosure_Lid", (0.88, 0.90, 0.93, 1.0), roughness=0.35)
mat_faceplate = create_material("Mat_Faceplate", (0.08, 0.11, 0.16, 1.0), roughness=0.25)
mat_accent = create_material("Mat_Cyan_Accent", (0.05, 0.65, 0.95, 1.0), roughness=0.2)
mat_esp32 = create_material("Mat_ESP32_PCB", (0.08, 0.25, 0.15, 1.0), roughness=0.4)
mat_pzem = create_material("Mat_PZEM_PCB", (0.05, 0.15, 0.35, 1.0), roughness=0.4)
mat_psu = create_material("Mat_HLK_PSU", (0.02, 0.02, 0.03, 1.0), roughness=0.5)
mat_brass = create_material("Mat_Brass_Terminal", (0.85, 0.65, 0.15, 1.0), roughness=0.2, metallic=0.9)

# Helper untuk membuat kubus sederhana
def add_box(name, size_x, size_y, size_z, loc_x, loc_y, loc_z, material=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(loc_x, loc_y, loc_z))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size_x, size_y, size_z)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    return obj

# Helper untuk silinder
def add_cylinder(name, radius, depth, loc_x, loc_y, loc_z, rot_x=0, rot_y=0, rot_z=0, vertices=32, material=None):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=(loc_x, loc_y, loc_z),
        rotation=(rot_x, rot_y, rot_z)
    )
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    return obj

# Helper Boolean Difference
def boolean_diff(target_obj, cutter_obj):
    mod = target_obj.modifiers.new(name="BoolDiff", type='BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter_obj
    mod.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target_obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter_obj, do_unlink=True)

# Helper Boolean Union
def boolean_union(target_obj, tool_obj):
    mod = target_obj.modifiers.new(name="BoolUnion", type='BOOLEAN')
    mod.operation = 'UNION'
    mod.object = tool_obj
    mod.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target_obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool_obj, do_unlink=True)

# ==========================================
# 1. ENCLOSURE BOTTOM BASE (Bagian Bawah)
# ==========================================
print("Mendesain Enclosure Base (Bagian Bawah)...")

# Dimensi Utama Casing
OUTER_L = 120.0  # Panjang (X)
OUTER_W = 82.0   # Lebar (Y)
BASE_H  = 26.0   # Tinggi base (Z)
WALL_T  = 2.5    # Tebal dinding
FLOOR_T = 2.5    # Tebal lantai

# Balok Luar Base
base_obj = add_box(
    "Enclosure_Bottom_Base",
    OUTER_L, OUTER_W, BASE_H,
    0, 0, BASE_H / 2.0,
    material=mat_base
)

# Pemotong Ruang Dalam (Hollowing)
inner_l = OUTER_L - (2 * WALL_T)
inner_w = OUTER_W - (2 * WALL_T)
inner_h = BASE_H - FLOOR_T + 2.0  # lebih tinggi sedikit agar terbuka atasnya
inner_cutter = add_box(
    "Inner_Cutter",
    inner_l, inner_w, inner_h,
    0, 0, FLOOR_T + (inner_h / 2.0)
)
boolean_diff(base_obj, inner_cutter)

# Dinding Sekat Isolasi (Safety Barrier AC vs DC)
# Sekat pada X = 5.0 mm memisahkan sisi PZEM/AC (X negatif) dan ESP32 (X positif)
barrier_t = 2.0
barrier_h = 22.0
barrier_obj = add_box(
    "Safety_Barrier",
    barrier_t, inner_w, barrier_h,
    5.0, 0, FLOOR_T + (barrier_h / 2.0),
    material=mat_base
)
# Buat celah kecil pada sekat untuk lewat kabel sinyal (UART 4 kabel)
wire_slot = add_box(
    "Wire_Slot",
    barrier_t + 2.0, 14.0, 8.0,
    5.0, 0, FLOOR_T + 4.0
)
boolean_diff(barrier_obj, wire_slot)
boolean_union(base_obj, barrier_obj)

# 4 Corner Screw Bosses (Tiang Sekrup Pengunci Tutup di Sudut)
corner_offset_x = (OUTER_L / 2.0) - 6.0
corner_offset_y = (OUTER_W / 2.0) - 6.0
boss_h = BASE_H - FLOOR_T

for cx, cy in [(-corner_offset_x, -corner_offset_y),
              (-corner_offset_x,  corner_offset_y),
              ( corner_offset_x, -corner_offset_y),
              ( corner_offset_x,  corner_offset_y)]:
    boss = add_cylinder(
        "Corner_Boss", radius=4.0, depth=boss_h,
        loc_x=cx, loc_y=cy, loc_z=FLOOR_T + (boss_h / 2.0),
        vertices=24, material=mat_base
    )
    boolean_union(base_obj, boss)
    
    # Lubang sekrup M3 (pilot hole 2.6mm untuk sekrup self-tapping M3)
    hole = add_cylinder(
        "Corner_Hole", radius=1.3, depth=boss_h + 2.0,
        loc_x=cx, loc_y=cy, loc_z=FLOOR_T + (boss_h / 2.0) + 1.0,
        vertices=16
    )
    boolean_diff(base_obj, hole)

# Standoffs ESP32 DevKit (Di sisi kanan: X positif)
# Jarak lubang ESP32 DevKit: ~48mm x 23mm
esp_center_x = 34.0
esp_center_y = 0.0
esp_standoff_h = 5.0
esp_pitch_x = 48.0
esp_pitch_y = 23.0

for sx in [-esp_pitch_x / 2.0, esp_pitch_x / 2.0]:
    for sy in [-esp_pitch_y / 2.0, esp_pitch_y / 2.0]:
        st = add_cylinder(
            "ESP_Standoff", radius=3.0, depth=esp_standoff_h,
            loc_x=esp_center_x + sx, loc_y=esp_center_y + sy,
            loc_z=FLOOR_T + (esp_standoff_h / 2.0),
            vertices=20, material=mat_base
        )
        boolean_union(base_obj, st)
        st_hole = add_cylinder(
            "ESP_Standoff_Hole", radius=1.1, depth=esp_standoff_h + 2.0,
            loc_x=esp_center_x + sx, loc_y=esp_center_y + sy,
            loc_z=FLOOR_T + (esp_standoff_h / 2.0) + 1.0,
            vertices=14
        )
        boolean_diff(base_obj, st_hole)

# Standoffs PZEM-004T v3.0 (Di sisi kiri: X negatif)
# Jarak lubang PZEM: ~67mm x 24mm
pzem_center_x = -26.0
pzem_center_y = 0.0
pzem_standoff_h = 5.0
pzem_pitch_x = 42.0  # mounting span yang pas di dalam chamber
pzem_pitch_y = 24.0

for px in [-pzem_pitch_x / 2.0, pzem_pitch_x / 2.0]:
    for py in [-pzem_pitch_y / 2.0, pzem_pitch_y / 2.0]:
        pst = add_cylinder(
            "PZEM_Standoff", radius=3.0, depth=pzem_standoff_h,
            loc_x=pzem_center_x + px, loc_y=pzem_center_y + py,
            loc_z=FLOOR_T + (pzem_standoff_h / 2.0),
            vertices=20, material=mat_base
        )
        boolean_union(base_obj, pst)
        pst_hole = add_cylinder(
            "PZEM_Hole", radius=1.2, depth=pzem_standoff_h + 2.0,
            loc_x=pzem_center_x + px, loc_y=pzem_center_y + py,
            loc_z=FLOOR_T + (pzem_standoff_h / 2.0) + 1.0,
            vertices=14
        )
        boolean_diff(base_obj, pst_hole)

# Cutout Port USB Micro/Type-C untuk ESP32 (Dinding Kanan: X = +OUTER_L/2)
usb_cutter = add_box(
    "USB_Cutout",
    WALL_T * 3.0, 13.0, 8.5,
    OUTER_L / 2.0, esp_center_y, FLOOR_T + esp_standoff_h + 5.0
)
boolean_diff(base_obj, usb_cutter)

# Cutout Kabel AC 220V Input (Dinding Kiri: X = -OUTER_L/2)
# Lubang ganda untuk kabel Fasa dan Netral yang aman berisolasi
ac_cutter1 = add_cylinder(
    "AC_Wire_Cutout1", radius=3.8, depth=WALL_T * 3.0,
    loc_x=-OUTER_L / 2.0, loc_y=-10.0, loc_z=16.0,
    rot_y=math.radians(90), vertices=24
)
boolean_diff(base_obj, ac_cutter1)

ac_cutter2 = add_cylinder(
    "AC_Wire_Cutout2", radius=3.8, depth=WALL_T * 3.0,
    loc_x=-OUTER_L / 2.0, loc_y=10.0, loc_z=16.0,
    rot_y=math.radians(90), vertices=24
)
boolean_diff(base_obj, ac_cutter2)

# Cutout Kabel Klem Sensor CT (Dinding Samping Atas: Y = +OUTER_W/2 di zona PZEM)
ct_cutter = add_cylinder(
    "CT_Wire_Cutout", radius=4.0, depth=WALL_T * 3.0,
    loc_x=-26.0, loc_y=OUTER_W / 2.0, loc_z=16.0,
    rot_x=math.radians(90), vertices=24
)
boolean_diff(base_obj, ct_cutter)

# External Mounting Ears / Flanges (Kuping Pemasangan Baut ke Dinding / Panel Kayu)
ear_w = 16.0
ear_ext = 12.0
ear_t = 3.5

for ex, dir_x in [(-OUTER_L/2.0 - ear_ext/2.0, -1), (OUTER_L/2.0 + ear_ext/2.0, 1)]:
    ear = add_box(
        "Mounting_Ear",
        ear_ext, ear_w, ear_t,
        ex, 0, ear_t / 2.0,
        material=mat_base
    )
    boolean_union(base_obj, ear)
    ear_hole = add_cylinder(
        "Ear_Hole", radius=2.3, depth=ear_t + 2.0,
        loc_x=ex, loc_y=0, loc_z=ear_t / 2.0,
        vertices=20
    )
    boolean_diff(base_obj, ear_hole)

# DIN Rail 35mm Mounting Channel di Bagian Dasar Bawah
# Standar DIN rail 35mm EN 50022 memiliki lebar 35mm dengan kedalaman rel 7.5mm
din_groove = add_box(
    "DIN_Channel",
    OUTER_L + 30.0, 36.0, 2.0,
    0, 0, 1.0
)
boolean_diff(base_obj, din_groove)

# ==========================================
# 2. ENCLOSURE TOP LID (Tutup Atas)
# ==========================================
print("Mendesain Enclosure Top Lid (Tutup Atas)...")

LID_H = 14.0
LID_TOP_T = 2.5

# Posisi vertikal Lid: diletakkan di atas Base dengan celah 12mm untuk visualisasi assembly
# Saat diekspor ke STL, masing-masing objek akan diposisikan flat di z=0 agar siap print.
LID_Z_OFFSET = BASE_H + 10.0

lid_obj = add_box(
    "Enclosure_Top_Lid",
    OUTER_L, OUTER_W, LID_H,
    0, 0, LID_Z_OFFSET + (LID_H / 2.0),
    material=mat_lid
)

# Pemotong Ruang Dalam Lid
lid_inner_h = LID_H - LID_TOP_T + 2.0
lid_cutter = add_box(
    "Lid_Inner_Cutter",
    inner_l, inner_w, lid_inner_h,
    0, 0, LID_Z_OFFSET + (lid_inner_h / 2.0) - 1.0
)
boolean_diff(lid_obj, lid_cutter)

# Bibir Pengunci (Interlocking Lip) agar pas masuk ke dalam base dengan rapi
lip_h = 2.5
lip_t = 1.2
lip_outer_l = inner_l - 0.4  # toleransi cetak 0.2mm per sisi
lip_outer_w = inner_w - 0.4
lip_inner_l = lip_outer_l - (2 * lip_t)
lip_inner_w = lip_outer_w - (2 * lip_t)

lip_outer = add_box(
    "Lip_Outer",
    lip_outer_l, lip_outer_w, lip_h,
    0, 0, LID_Z_OFFSET - (lip_h / 2.0),
    material=mat_lid
)
lip_inner = add_box(
    "Lip_Inner",
    lip_inner_l, lip_inner_w, lip_h + 2.0,
    0, 0, LID_Z_OFFSET - (lip_h / 2.0)
)
boolean_diff(lip_outer, lip_inner)
boolean_union(lid_obj, lip_outer)

# Lubang Baut Countersunk M3 di Sudut Tutup
for cx, cy in [(-corner_offset_x, -corner_offset_y),
              (-corner_offset_x,  corner_offset_y),
              ( corner_offset_x, -corner_offset_y),
              ( corner_offset_x,  corner_offset_y)]:
    # Lubang tembus baut 3.3mm
    bolt_hole = add_cylinder(
        "Lid_Bolt_Hole", radius=1.7, depth=LID_H + 6.0,
        loc_x=cx, loc_y=cy, loc_z=LID_Z_OFFSET + (LID_H / 2.0),
        vertices=20
    )
    boolean_diff(lid_obj, bolt_hole)
    # Countersink lubang kepala baut (6.2mm x kedalaman 2.0mm)
    csink = add_cylinder(
        "Countersink", radius=3.2, depth=3.0,
        loc_x=cx, loc_y=cy, loc_z=LID_Z_OFFSET + LID_H - 1.0,
        vertices=24
    )
    boolean_diff(lid_obj, csink)

# Kisi Ventilasi Udara (Air Cooling Grilles)
vent_slot_len = 34.0
vent_slot_w = 2.2
vent_pitch = 4.5

for i in range(-4, 5):
    vy = i * vent_pitch
    vent_cut = add_box(
        f"Vent_Slot_{i}",
        vent_slot_len, vent_slot_w, LID_TOP_T + 4.0,
        -18.0, vy, LID_Z_OFFSET + LID_H - (LID_TOP_T / 2.0)
    )
    boolean_diff(lid_obj, vent_cut)

# 3 Lubang Indikator Status LED (PWR, WIFI, DATA)
led_labels = [("PWR", -12.0), ("WIFI", 0.0), ("DATA", 12.0)]
for name, ly in led_labels:
    led_h = add_cylinder(
        f"LED_{name}", radius=1.7, depth=LID_TOP_T + 4.0,
        loc_x=34.0, loc_y=ly, loc_z=LID_Z_OFFSET + LID_H - (LID_TOP_T / 2.0),
        vertices=20
    )
    boolean_diff(lid_obj, led_h)

# Plat Label Depan (Faceplate Recess)
faceplate = add_box(
    "Faceplate_Plate",
    48.0, 36.0, 0.8,
    34.0, 0, LID_Z_OFFSET + LID_H + 0.4,
    material=mat_faceplate
)

# ==========================================
# 3. DUMMY ELECTRONIC MODULES (Untuk Visualisasi)
# ==========================================
print("Menambahkan Komponen Elektronik Dummies untuk Fit-Check...")

# ESP32 Board
esp_board = add_box(
    "Dummy_ESP32_DevKit",
    51.5, 28.5, 1.6,
    esp_center_x, esp_center_y, FLOOR_T + esp_standoff_h + 0.8,
    material=mat_esp32
)
# ESP32 Metal Shield
esp_shield = add_box(
    "ESP32_Metal_Can",
    18.0, 16.0, 3.2,
    esp_center_x - 10.0, esp_center_y, FLOOR_T + esp_standoff_h + 1.6 + 1.6,
    material=mat_base
)
# ESP32 USB Port
esp_usb = add_box(
    "ESP32_USB_Port",
    8.0, 7.5, 3.0,
    esp_center_x + 22.0, esp_center_y, FLOOR_T + esp_standoff_h + 1.6 + 1.5,
    material=mat_brass
)

# PZEM-004T v3.0 Board
pzem_board = add_box(
    "Dummy_PZEM004T",
    72.0, 31.0, 1.6,
    pzem_center_x, pzem_center_y, FLOOR_T + pzem_standoff_h + 0.8,
    material=mat_pzem
)
# PZEM Terminal AC 2-Pin
pzem_term_ac = add_box(
    "PZEM_Terminal_AC",
    10.0, 15.0, 11.0,
    pzem_center_x - 29.0, pzem_center_y, FLOOR_T + pzem_standoff_h + 1.6 + 5.5,
    material=mat_faceplate
)
# PZEM Optocouplers
pzem_optos = add_box(
    "PZEM_Optocouplers",
    12.0, 8.0, 4.0,
    pzem_center_x + 10.0, pzem_center_y, FLOOR_T + pzem_standoff_h + 1.6 + 2.0,
    material=mat_faceplate
)

# HLK-PM01 Isolated AC-DC Step-Down Module (5V 3W)
hlk_module = add_box(
    "Dummy_HLK_PM01",
    34.0, 20.0, 15.0,
    -18.0, 24.0, FLOOR_T + 7.5,
    material=mat_psu
)

# ==========================================
# 4. ORGANISASI KOLEKSI BLENDER
# ==========================================
print("Mengelompokkan Objek ke Koleksi...")

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
move_to_collection(faceplate, "Enclosure_Lid")

for dummy in [esp_board, esp_shield, esp_usb, pzem_board, pzem_term_ac, pzem_optos, hlk_module]:
    move_to_collection(dummy, "Electronics_Reference")

# ==========================================
# 5. EKSPOR MODEL STL UNTUK JASA CETAK 3D
# ==========================================
print("Mengekspor Berkas STL Siap Cetak...")

# Helper untuk ekspor seleksi objek
def export_selected_stl(objects_to_export, filepath, orient_for_print=True):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects_to_export:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects_to_export[0]
    
    # Simpan posisi asli
    orig_transforms = []
    for o in objects_to_export:
        orig_transforms.append((o, o.location.copy(), o.rotation_euler.copy()))
        
    if orient_for_print and "Lid" in filepath:
        # Orientasikan Top Lid telungkup rata di Z=0 (wajah atas menyentuh build plate agar hasil mulus)
        for o in objects_to_export:
            o.rotation_euler = (math.radians(180), 0, 0)
            o.location = (0, 0, LID_H)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    # Ekspor STL menggunakan operator Blender
    bpy.ops.wm.stl_export(
        filepath=filepath,
        export_selected_objects=True
    )
    print(f"-> Berhasil diekspor: {filepath}")

    # Kembalikan posisi asli untuk view visual di .blend
    for o, orig_loc, orig_rot in orig_transforms:
        o.location = orig_loc
        o.rotation_euler = orig_rot

# 1. Ekspor Bottom Base STL
base_stl_path = os.path.join(EXPORT_DIR, "enclosure_bottom_base.stl")
export_selected_stl([base_obj], base_stl_path, orient_for_print=False)

# 2. Ekspor Top Lid STL
lid_stl_path = os.path.join(EXPORT_DIR, "enclosure_top_lid.stl")
export_selected_stl([lid_obj], lid_stl_path, orient_for_print=True)

# 3. Ekspor Full Assembly STL (Preview Casing Lengkap)
assembly_stl_path = os.path.join(EXPORT_DIR, "enclosure_assembly_preview.stl")
export_selected_stl([base_obj, lid_obj, faceplate], assembly_stl_path, orient_for_print=False)

# ==========================================
# 6. SETUP KAMERA & LIGHTING UNTUK PREVIEW
# ==========================================
print("Mengatur Kamera dan Render Preview...")

# Tambah Lampu Studio (Key, Fill, Rim)
bpy.ops.object.light_add(type='SUN', location=(100, -120, 200))
sun1 = bpy.context.active_object
sun1.name = "Key_Light"
sun1.data.energy = 4.0
sun1.data.color = (1.0, 0.98, 0.95)

bpy.ops.object.light_add(type='POINT', location=(-120, 100, 120))
fill = bpy.context.active_object
fill.name = "Fill_Light"
fill.data.energy = 40.0
fill.data.color = (0.7, 0.85, 1.0)

# Tambah Kamera Isometrik 3D
bpy.ops.object.camera_add(
    location=(190, -210, 180),
    rotation=(math.radians(58), 0, math.radians(42))
)
cam = bpy.context.active_object
cam.name = "Main_Camera"
scene.camera = cam

# Set Resolusi Render
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = 'PNG'
preview_img_path = os.path.join(CURRENT_DIR, "render_preview.png")
scene.render.filepath = preview_img_path

# Render satu frame preview
try:
    bpy.ops.render.render(write_still=True)
    print(f"-> Render preview tersimpan di: {preview_img_path}")
except Exception as e:
    print(f"Render catatan: {e}")

# ==========================================
# 7. SIMPAN FILE BLENDER (.BLEND)
# ==========================================
blend_file_path = os.path.join(CURRENT_DIR, "energy_monitor_case.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_file_path)
print(f"-> Proyek Blender berhasil disimpan di: {blend_file_path}")
print("Selesai! Seluruh aset 3D berhasil dibuat.")

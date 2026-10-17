"""Blender headless script for ultra-realistic Cycles rendering of LDraw models."""

import os
import sys
import math
import bpy

def render_model(
    ldr_path: str,
    output_png: str,
    azimuth_deg: float = 215.0,
    elevation_deg: float = 28.0,
    resolution_x: int = 1920,
    resolution_y: int = 1080,
    samples: int = 128,
    use_cycles: bool = True
):
    print(f"Loading {ldr_path}...")
    ldraw_zip = os.path.expanduser("~/complete.zip")

    import addon_utils
    addon_utils.enable("io_scene_importldraw")
    addon_utils.enable("cycles")

    # Clear initial objects
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)

    # Import LDraw model with realistic features
    bpy.ops.import_scene.importldraw(
        filepath=os.path.abspath(ldr_path),
        ldrawPath=ldraw_zip,
        addEnvironment=True,
        positionCamera=True,
        useLogoStuds=True,
        bevelEdges=True,
        bakeBevels=True,
        smoothParts=True,
        look="normal",
        colourScheme="lgeo"
    )

    scene = bpy.context.scene

    # Find bounding box / center of the LEGO model
    mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name != 'LegoGroundPlane']
    if not mesh_objs:
        print("No mesh objects found!")
        return

    min_x = min(o.location.x for o in mesh_objs)
    max_x = max(o.location.x for o in mesh_objs)
    min_y = min(o.location.y for o in mesh_objs)
    max_y = max(o.location.y for o in mesh_objs)
    min_z = min(o.location.z for o in mesh_objs)
    max_z = max(o.location.z for o in mesh_objs)

    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    center_z = (min_z + max_z) / 2.0
    model_size = max(max_x - min_x, max_y - min_y, max_z - min_z)

    print(f"Model bounds: X=[{min_x:.3f}, {max_x:.3f}], Y=[{min_y:.3f}, {max_y:.3f}], Z=[{min_z:.3f}, {max_z:.3f}]")
    print(f"Center: ({center_x:.3f}, {center_y:.3f}, {center_z:.3f}), size={model_size:.3f}")

    from mathutils import Vector

    # Camera positioning
    cam_obj = bpy.data.objects.get("Camera")
    if not cam_obj:
        cam_data = bpy.data.cameras.new("RenderCam")
        cam_obj = bpy.data.objects.new("Camera", cam_data)
        scene.collection.objects.link(cam_obj)

    scene.camera = cam_obj
    cam = cam_obj.data
    cam.lens = 55  # 55mm focal length
    cam.clip_start = 0.01
    cam.clip_end = 100.0

    target = Vector((center_x, center_y, center_z * 0.9))

    # In Blender imported LDraw: -Y is front, +Y is rear, -X is left, +X is right, +Z is up
    # azimuth_deg: 0 = front (-Y), 90 = right (+X), 180 = rear (+Y), 270 = left (-X)
    # So front-left is around 315 deg (-X, -Y) or specify directly
    # Or:
    # front-left: X < 0, Y < 0
    # front-right: X > 0, Y < 0
    az_rad = math.radians(azimuth_deg)
    el_rad = math.radians(elevation_deg)
    dist = model_size * 2.65

    cam_x = center_x + dist * math.cos(el_rad) * math.sin(az_rad)
    cam_y = center_y - dist * math.cos(el_rad) * math.cos(az_rad)
    cam_z = center_z + dist * math.sin(el_rad)

    cam_pos = Vector((cam_x, cam_y, cam_z))
    cam_obj.location = cam_pos

    direction = target - cam_pos
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    # Lighting enhancement
    # Soft warm main sun/key light
    for l in [o for o in bpy.data.objects if o.type == 'LIGHT']:
        l.data.energy = 60.0
        l.data.shadow_soft_size = 0.25

    # Add fill light for balanced shadow detail
    fill_data = bpy.data.lights.new(name="FillLight", type='POINT')
    fill_data.energy = 30.0
    fill_data.color = (0.88, 0.93, 1.0)
    fill_data.shadow_soft_size = 0.5
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    fill_obj.location = (center_x - dist * 0.7, center_y - dist * 0.4, center_z + dist * 0.6)
    scene.collection.objects.link(fill_obj)

    # World / background environment
    world = scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs['Color'].default_value = (0.95, 0.95, 0.96, 1.0)
        bg_node.inputs['Strength'].default_value = 1.0

    # Ensure ground plane sits right under baseplate
    ground = bpy.data.objects.get("LegoGroundPlane")
    if ground:
        ground.location.z = min_z - 0.001

    # Render settings
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'

    if use_cycles:
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'GPU'
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True

        try:
            prefs = bpy.context.preferences.addons['cycles'].preferences
            prefs.compute_device_type = 'METAL'
            for dev in prefs.devices:
                dev.use = True
                print(f"Cycles device: {dev.name} ({dev.type})")
        except Exception as e:
            print(f"Metal GPU setup notice: {e}")
            scene.cycles.device = 'CPU'

    scene.render.filepath = os.path.abspath(output_png)
    os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)

    print(f"Rendering to {output_png} ({resolution_x}x{resolution_y}, {samples} samples)...")
    bpy.ops.render.render(write_still=True)
    print("Render finished successfully!")

if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) < 2:
        print("Usage: blender --background --python blender_render.py -- <ldr_path> <output_png> [azimuth] [elevation] [samples]")
        sys.exit(1)

    ldr_file = args[0]
    out_file = args[1]
    az = float(args[2]) if len(args) > 2 else 215.0
    el = float(args[3]) if len(args) > 3 else 28.0
    smp = int(args[4]) if len(args) > 4 else 128

    render_model(ldr_file, out_file, azimuth_deg=az, elevation_deg=el, samples=smp)

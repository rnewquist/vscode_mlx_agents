# Shared Discovery Memory: Blender Python API Scripts

This file is a shared, real-time workspace for the `scoper` and `architect` subagents. Use it to log findings, list files analyzed, avoid duplicate commands, and coordinate findings to build the Combined Discovery Report.

## Scoper Activity Log
- [x] Initialize scoping task
- [x] Scan `qwen_lora/blender_info` directory for HTML documentation files
- [x] Validate API sections against Sphinx build pages
- [x] Document codebase entrypoints and utility modules
  - Scoped `qwen_lora/blender_info/bpy.context.html` (context queries: active object, camera, viewport area)
  - Scoped `qwen_lora/blender_info/bpy.data.html` (database collections, `bpy.data.orphans_purge()`)
  - Scoped `qwen_lora/blender_info/bpy.ops.html` (operators: modifier_add, collections, primitives)
  - Scoped `qwen_lora/blender_info/bmesh.html` (low-level mesh edits: `bmesh.new()`, geometry operations, normal recalculations)
  - Scoped `qwen_lora/blender_info/bpy.types.html` & `bpy.props.html` (Add-on registration: Operators, Panels, PropertyGroups, `bpy.utils.register_class()`)
  - Scoped `qwen_lora/blender_info/bpy.app.handlers.html` & `bpy.app.timers.html` (Render callbacks: `render_pre`, `render_post`, and standard timers)
  - Scoped `qwen_lora/blender_info/bpy.msgbus.html` (Reactive events: `bpy.msgbus.subscribe_rna()`, RNA path notifications)
  - Scoped `qwen_lora/blender_info/bl_math.html` & `mathutils.html` (Math libraries: Vector, Matrix, and `bl_math.noise.noise`)
  - Scoped `qwen_lora/blender_info/bpy_extras.html` (Viewport utilities: `world_to_camera_view` screen coordinates)

## Architect Activity Log
- [x] Initialize architectural briefing
- [x] Outline design patterns for standard operators, low-level BMesh edits, background timers, custom properties/UIs, and message bus subscriptions
- [x] Design structural blueprint for the 9 distinct python scripts
- [x] Define coding standards, error handling strategies, and modular patterns for Blender 4.1+
- [x] Establish register/unregister boilerplate for custom panels
- [x] Define handler registration patterns with persistence

## Combined Scoped Architecture & Blueprint

### 1. Architectural Design Standards (Blender 4.1+)
- **Modern API Compliance**: Avoid deprecated features. Never use `use_auto_smooth`. Instead, use `bpy.ops.object.shade_smooth_by_angle(angle=...)` or direct mesh auto-smooth properties matching modern Blender.
- **Defensive Design**: Scripts must be runnable multiple times without crashing or spawning duplicate handlers, timers, or registered classes. Always clear existing handlers/timers and unregister classes before registering them again.
- **BMesh Lifecycle Management**: Every `bmesh.new()` must have a matching `bm.free()` (either explicitly or via a context manager) to avoid memory leaks.
- **Namespaces**: Keep imports clean: `import bpy`, `import bmesh`, `import mathutils`, `import bl_math`.

---

### 2. Blueprints for the 9 Scripts

#### 1. `context_inspector.py` (API: `bpy.context`)
- **Imports**: `import bpy`
- **Logic**: 
  - Log active object, select count, active camera, 3D cursor position, active workspace, and viewport areas.
  - If active camera is unset, search `bpy.data.cameras` / `bpy.data.objects`, bind the first found camera to the active scene, and print the name.
  - Relocate the 3D cursor to the exact center of the active object.

#### 2. `data_cleaner.py` (API: `bpy.data`)
- **Imports**: `import bpy`
- **Logic**:
  - Scan the entire project database. Count objects, meshes, materials, images, textures, and cameras.
  - List all objects in the active scene, their type, and associated material slots.
  - Run `bpy.data.orphans_purge()` to cleanly delete unused data-blocks with 0 users.
  - Print the clean-up report, showing the count of deleted elements.

#### 3. `ops_procedural_city.py` (API: `bpy.ops`)
- **Imports**: `import bpy`, `import random`
- **Logic**:
  - Create a new collection named `"Procedural City"`. Link it to the scene.
  - Iterate over a 4x4 grid: spawn a cube primitive at each coordinate using `bpy.ops.mesh.primitive_cube_add()`.
  - Scale the height of each cube randomly to simulate a building.
  - Apply a bevel modifier using `bpy.ops.object.modifier_add(type='BEVEL')` and configure properties.
  - Assign a standard base material.

#### 4. `bmesh_star_generator.py` (API: `bmesh`)
- **Imports**: `import bpy`, `import bmesh`, `import math`
- **Logic**:
  - Use `bmesh.new()` to initialize an in-memory mesh.
  - Mathematically compute vertices of a 5-pointed star (outer points, inner points, alternating angles).
  - Connect outer and inner vertices to form a central hub and outer spikes, creating faces with `bm.faces.new()`.
  - Extrude the entire set of faces along the Z-axis by 0.5 units using `bmesh.ops.extrude_face_region()`.
  - Recalculate face normals using `bmesh.ops.recalculate_face_normals()`.
  - Write BMesh into a new mesh block, bind to a new object, link to the scene, and call `bm.free()`.

#### 5. `custom_tool_properties.py` (API: `bpy.types`, `bpy.props`, `bpy.utils`)
- **Imports**: `import bpy`
- **Logic**:
  - Define custom scene variables: `bpy.props.StringProperty`, `bpy.props.EnumProperty`, `bpy.props.IntProperty`, `bpy.props.BoolProperty`.
  - Implement a custom Operator `OBJECT_OT_validate_metadata` that prints and logs these scene variables.
  - Register a custom Panel `VIEW3D_PT_pipeline_panel` in the 3D Viewport's sidebar under category `"Pipeline"`.
  - Bind custom inputs to the layout to display text, drop-downs, integer sliders, checkboxes, and the operator button.

#### 6. `app_render_handlers.py` (API: `bpy.app.handlers`, `bpy.app.timers`)
- **Imports**: `import bpy`
- **Logic**:
  - Define render callback functions: `render_pre_callback(scene)` and `render_post_callback(scene)`.
  - Safely append callbacks to `bpy.app.handlers.render_pre` and `render_post` (remove any duplicates first to ensure a clean run).
  - Define a periodic timer callback `poly_watchdog_timer()` that checks if the total vertices in the active scene exceed 100,000, printing a warning. Return `5.0` to run every 5 seconds.
  - Register the timer using `bpy.app.timers.register(poly_watchdog_timer)`.

#### 7. `msgbus_transform_notifier.py` (API: `bpy.msgbus`)
- **Imports**: `import bpy`
- **Logic**:
  - Set up an RNA change listener using `bpy.msgbus.subscribe_rna()`.
  - Target the active object's location property or focal length of active camera.
  - Provide a hook callback `on_transform_change(*args)` that prints the updated location/rotation values to the terminal.
  - Store a persistent reference to the subscription key to prevent Python garbage collection from destroying the event listener.

#### 8. `math_terrain_displacer.py` (API: `bl_math.noise`, `mathutils`)
- **Imports**: `import bpy`, `import mathutils`, `import bl_math`, `import math`
- **Logic**:
  - Create a high-density plane grid using operators or BMesh.
  - Loop over vertices, compute a procedural Z-height using fractal noise `bl_math.noise.noise(mathutils.Vector((x, y, 0)) * frequency) * amplitude`.
  - Use `mathutils.Vector` and matrices to place a separate "target" object (e.g. a lighthouse or beacon cone) at the terrain's surface and orient its orientation vector to align with the local terrain surface normal.

#### 9. `extras_align_to_camera.py` (API: `bpy_extras.object_utils`, `bpy_extras.view3d_utils`)
- **Imports**: `import bpy`, `import bpy_extras`, `import mathutils`
- **Logic**:
  - Locate the active camera object and a flat "billboard plane" target object.
  - Use `bpy_extras.object_utils.world_to_camera_view` to project the billboard center coordinate into 2D camera viewport coordinates (X, Y in range [0, 1]).
  - Orient the billboard's rotation matrix so its normal vector is perfectly aligned with the camera's view vector (facing the camera directly).

---

## 3. Scoping Webview UI for Blender Gemini Integration
- **Context**: The `mlx/mlx-chat/webview-ui` codebase is a premium React/TypeScript front-end designed to communicate with local models and agents.
- **Parity & Feasibility**:
  - The UI uses browser-native relative HTTP requests (`API_BASE = ""`) in browser mode, matching perfectly with the standard Python HTTP server implemented in `web_server.py` of the Blender Gemini Plugin.
  - Successfully mapped backend state keys: `messages`, `status`, `logs`, `pendingDiffs`, `artifacts`, `telemetry`, `serverStatus`, and `modelsConfig`.
- **Modifications Planned/Executed**:
  - Exported Vite React compilation configuration to avoid hash-based filenames, maintaining static file names `index.js` and `index.css` under the assets path.
  - Customized branding from "MLX Chat" to "Blender Gemini Chat" / "Blender AI Orchestrator".
  - Omitted custom model additions/deletions which are handled natively on the Blender/Ollama backend layer.

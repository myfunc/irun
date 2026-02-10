# IVAN Shader Catalog

All runtime GLSL files live under this directory.

## Layout

```text
assets/shaders/
├── README.md
└── world/
    ├── lightmap_120.vert
    └── lightmap_120.frag
```

## Catalog Source of Truth

Shader ids and file bindings are defined in:

- `apps/ivan/src/ivan/render/shader_catalog.py`

Current ids:

- `world.lightmap.glsl120` -> `world/lightmap_120.vert` + `world/lightmap_120.frag`

## Conventions

- Keep one shader program per `*.vert` + `*.frag` pair.
- Prefer explicit versioned filenames when compatibility matters (`*_120` etc.).
- Add new entries to `shader_catalog.py` before wiring usage in gameplay code.


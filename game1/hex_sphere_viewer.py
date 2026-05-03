"""Static viewer export for the procedural hex sphere."""

from __future__ import annotations

import json
from pathlib import Path

from .hex_sphere import HexSphereMesh


def render_viewer_html(mesh: HexSphereMesh) -> str:
    payload = json.dumps(
        mesh.to_render_payload(),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return _VIEWER_TEMPLATE.replace("__MESH_PAYLOAD__", payload)


def write_viewer_html(path: str | Path, mesh: HexSphereMesh) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_viewer_html(mesh), encoding="utf-8")
    return output_path


_VIEWER_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>ISEA3H Planet Mesh</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      background: #f5f6f1;
      color: #1f2722;
    }

    * {
      box-sizing: border-box;
    }

    html,
    body {
      margin: 0;
      min-height: 100%;
      overflow: hidden;
    }

    body {
      background:
        radial-gradient(circle at 28% 22%, rgba(255, 255, 255, 0.86), transparent 32%),
        linear-gradient(145deg, #f8f8f3 0%, #e4e9df 54%, #cfd8d5 100%);
    }

    canvas {
      display: block;
      width: 100vw;
      height: 100vh;
      cursor: grab;
      touch-action: none;
    }

    canvas:active {
      cursor: grabbing;
    }

    .hud {
      position: fixed;
      top: 14px;
      left: 14px;
      display: grid;
      gap: 8px;
      pointer-events: none;
      user-select: none;
    }

    .panel {
      min-height: 34px;
      padding: 8px 10px;
      border: 1px solid rgba(31, 39, 34, 0.14);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.74);
      box-shadow: 0 8px 26px rgba(31, 39, 34, 0.10);
      backdrop-filter: blur(12px);
      font-size: 12px;
      line-height: 1.35;
      letter-spacing: 0;
      white-space: nowrap;
    }

    .tools {
      position: fixed;
      right: 14px;
      top: 14px;
      display: flex;
      gap: 8px;
    }

    button {
      width: 34px;
      height: 34px;
      border: 1px solid rgba(31, 39, 34, 0.18);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.78);
      color: #1f2722;
      font: 700 18px/1 ui-sans-serif, system-ui, sans-serif;
      box-shadow: 0 8px 26px rgba(31, 39, 34, 0.10);
      cursor: pointer;
      backdrop-filter: blur(12px);
    }

    button:hover {
      background: #ffffff;
    }

    @media (max-width: 560px) {
      .hud {
        top: 10px;
        left: 10px;
        max-width: calc(100vw - 72px);
      }

      .panel {
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .tools {
        top: 10px;
        right: 10px;
        flex-direction: column;
      }
    }
  </style>
</head>
<body>
  <canvas id="planet"></canvas>
  <div class="hud" aria-live="polite">
    <div class="panel" id="stats"></div>
    <div class="panel" id="selection"></div>
  </div>
  <div class="tools">
    <button id="zoomIn" title="Zoom in" aria-label="Zoom in">+</button>
    <button id="zoomOut" title="Zoom out" aria-label="Zoom out">-</button>
    <button id="reset" title="Reset camera" aria-label="Reset camera">R</button>
  </div>

  <script>
    const payload = __MESH_PAYLOAD__;
    const canvas = document.getElementById("planet");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const stats = document.getElementById("stats");
    const selection = document.getElementById("selection");
    const cells = payload.chunks.flatMap((chunk) => chunk.cells);
    const colors = {
      polar: "#e9f3f5",
      tundra: "#a7b8a0",
      boreal: "#527f63",
      temperate: "#78a65d",
      steppe: "#c7b464",
      desert: "#d7a85c",
      tropical: "#2f9964",
      ocean: "#4f8fb3"
    };
    const light = normalize([-0.45, -0.52, 0.72]);

    let width = 0;
    let height = 0;
    let rotationX = -0.28;
    let rotationY = 0.54;
    let zoom = 1.0;
    let dragging = false;
    let pointerX = 0;
    let pointerY = 0;
    let screenCells = [];
    let selectedCell = cells[0];

    stats.textContent = `ISEA3H r${payload.grid.resolution} | ${payload.grid.renderCellCount} cells | ${payload.chunks.length} chunks`;
    updateSelection(selectedCell);

    function resize() {
      const scale = window.devicePixelRatio || 1;
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * scale);
      canvas.height = Math.floor(height * scale);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      draw();
    }

    function draw() {
      ctx.clearRect(0, 0, width, height);
      const radius = Math.min(width, height) * 0.42 * zoom;
      const cx = width * 0.5;
      const cy = height * 0.54;
      screenCells = [];

      const drawable = cells
        .map((cell) => {
          const center = rotate(cell.center);
          return { cell, center };
        })
        .filter((item) => item.center[2] > -0.24)
        .sort((a, b) => a.center[2] - b.center[2]);

      for (const item of drawable) {
        const cell = item.cell;
        const center = item.center;
        const elevation = Math.max(-220, cell.elevationM) / 90000;
        const points = cell.boundary.map((vertex) => {
          const elevated = scaleVec(vertex, 1 + elevation);
          const rotated = rotate(elevated);
          return project(rotated, cx, cy, radius);
        });
        const shade = 0.66 + Math.max(0, dot(normalize(center), light)) * 0.34;
        const base = colors[cell.biome] || "#8f9b8b";
        drawPolygon(points, shadeColor(base, shade), center[2]);
        screenCells.push({ cell, points, z: center[2] });
      }

      const atmosphere = ctx.createRadialGradient(cx, cy, radius * 0.20, cx, cy, radius * 1.12);
      atmosphere.addColorStop(0, "rgba(255, 255, 255, 0)");
      atmosphere.addColorStop(0.74, "rgba(255, 255, 255, 0)");
      atmosphere.addColorStop(1, "rgba(255, 255, 255, 0.48)");
      ctx.beginPath();
      ctx.arc(cx, cy, radius * 1.012, 0, Math.PI * 2);
      ctx.fillStyle = atmosphere;
      ctx.fill();
    }

    function drawPolygon(points, fill, z) {
      if (points.length < 3) return;
      ctx.beginPath();
      ctx.moveTo(points[0][0], points[0][1]);
      for (let i = 1; i < points.length; i += 1) {
        ctx.lineTo(points[i][0], points[i][1]);
      }
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.strokeStyle = `rgba(27, 38, 32, ${0.12 + Math.max(0, z) * 0.18})`;
      ctx.lineWidth = 0.7;
      ctx.stroke();
    }

    function rotate(v) {
      const sx = Math.sin(rotationX);
      const cx = Math.cos(rotationX);
      const sy = Math.sin(rotationY);
      const cy = Math.cos(rotationY);
      const y1 = v[1] * cx - v[2] * sx;
      const z1 = v[1] * sx + v[2] * cx;
      const x2 = v[0] * cy + z1 * sy;
      const z2 = -v[0] * sy + z1 * cy;
      return [x2, y1, z2];
    }

    function project(v, cx, cy, radius) {
      const perspective = 2.7 / (2.7 - v[2] * 0.38);
      return [cx + v[0] * radius * perspective, cy - v[1] * radius * perspective];
    }

    function shadeColor(hex, factor) {
      const n = parseInt(hex.slice(1), 16);
      const r = Math.min(255, Math.round(((n >> 16) & 255) * factor));
      const g = Math.min(255, Math.round(((n >> 8) & 255) * factor));
      const b = Math.min(255, Math.round((n & 255) * factor));
      return `rgb(${r}, ${g}, ${b})`;
    }

    function normalize(v) {
      const length = Math.hypot(v[0], v[1], v[2]);
      return [v[0] / length, v[1] / length, v[2] / length];
    }

    function scaleVec(v, scale) {
      return [v[0] * scale, v[1] * scale, v[2] * scale];
    }

    function dot(a, b) {
      return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    }

    function pointInPolygon(point, polygon) {
      let inside = false;
      for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i, i += 1) {
        const xi = polygon[i][0], yi = polygon[i][1];
        const xj = polygon[j][0], yj = polygon[j][1];
        const intersects = ((yi > point[1]) !== (yj > point[1])) &&
          (point[0] < (xj - xi) * (point[1] - yi) / (yj - yi + Number.EPSILON) + xi);
        if (intersects) inside = !inside;
      }
      return inside;
    }

    function pick(x, y) {
      for (let i = screenCells.length - 1; i >= 0; i -= 1) {
        const item = screenCells[i];
        if (pointInPolygon([x, y], item.points)) {
          selectedCell = item.cell;
          updateSelection(selectedCell);
          return;
        }
      }
    }

    function updateSelection(cell) {
      if (!cell) {
        selection.textContent = "";
        return;
      }
      selection.textContent = `${cell.token} | ${cell.biome} | ${Math.round(cell.elevationM)} m`;
    }

    canvas.addEventListener("pointerdown", (event) => {
      dragging = true;
      pointerX = event.clientX;
      pointerY = event.clientY;
      canvas.setPointerCapture(event.pointerId);
    });

    canvas.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      const dx = event.clientX - pointerX;
      const dy = event.clientY - pointerY;
      pointerX = event.clientX;
      pointerY = event.clientY;
      rotationY += dx * 0.008;
      rotationX = Math.max(-1.35, Math.min(1.35, rotationX + dy * 0.008));
      draw();
    });

    canvas.addEventListener("pointerup", (event) => {
      dragging = false;
      pick(event.clientX, event.clientY);
    });

    canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      zoom = Math.max(0.55, Math.min(2.4, zoom * (event.deltaY > 0 ? 0.92 : 1.08)));
      draw();
    }, { passive: false });

    document.getElementById("zoomIn").addEventListener("click", () => {
      zoom = Math.min(2.4, zoom * 1.12);
      draw();
    });

    document.getElementById("zoomOut").addEventListener("click", () => {
      zoom = Math.max(0.55, zoom / 1.12);
      draw();
    });

    document.getElementById("reset").addEventListener("click", () => {
      rotationX = -0.28;
      rotationY = 0.54;
      zoom = 1.0;
      draw();
    });

    window.addEventListener("resize", resize);
    resize();
  </script>
</body>
</html>
"""

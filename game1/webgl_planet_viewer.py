"""Static WebGL viewer for the spherical point cloud.

Issue #11 asks the v0.0.4 viewer to drop the 2D-canvas polygon mesh and move
to true 3D rendering of millions of points in spherical coordinates. This
module produces a single self-contained HTML file that:

- ships every payload (points, biomes, elevations) inside the page so the
  file can be opened from disk without a server, just like the v0.0.3
  ``hex_sphere_viewer.html``;
- renders the cloud with raw WebGL2 (no Three.js, no external CDN), so the
  Python core's "no third-party runtime dependency" policy still holds;
- supports several LOD levels and switches between them on zoom, so a level
  with millions of points can replace the 2 000-point default at the highest
  zoom without ever loading the dense buffers when the camera is far;
- keeps the WASD/QE/+/-/R control scheme from v0.0.3 so muscle memory
  carries over.
"""

from __future__ import annotations

import json
from pathlib import Path

from .sphere_points import SpherePointPayload, build_sphere_point_payload


def render_webgl_viewer_html(payload: SpherePointPayload | dict[str, object]) -> str:
    """Render a self-contained HTML viewer for a sphere-point payload."""

    if isinstance(payload, SpherePointPayload):
        rendered = payload.to_render_payload()
    else:
        rendered = dict(payload)
        if rendered.get("kind") != "sphere-points-lod":
            raise ValueError(
                "payload must be produced by build_sphere_point_payload"
            )

    serialised = json.dumps(rendered, ensure_ascii=True, separators=(",", ":"))
    return _VIEWER_TEMPLATE.replace("__SPHERE_PAYLOAD__", serialised)


def write_webgl_viewer_html(
    path: str | Path,
    payload: SpherePointPayload | dict[str, object] | None = None,
    *,
    counts: tuple[int, ...] = (2_000, 20_000, 200_000),
    target_logical_count: int = 10_000_000,
) -> Path:
    """Render the WebGL viewer HTML to ``path`` and return the final path."""

    if payload is None:
        payload = build_sphere_point_payload(
            counts=counts,
            target_logical_count=target_logical_count,
        )
    html = render_webgl_viewer_html(payload)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


_VIEWER_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>Spherical Point Planet (WebGL)</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      background: #05080d;
      color: #e6ecf2;
    }

    * { box-sizing: border-box; }

    html, body {
      margin: 0;
      min-height: 100%;
      overflow: hidden;
      background: radial-gradient(circle at 30% 30%, #0e1a2c 0%, #05080d 70%);
    }

    canvas {
      display: block;
      width: 100vw;
      height: 100vh;
      cursor: grab;
      touch-action: none;
      outline: none;
    }

    canvas:active { cursor: grabbing; }

    #planet {
      position: fixed;
      inset: 0;
      z-index: 0;
    }

    #gridOverlay {
      position: fixed;
      inset: 0;
      z-index: 1;
      pointer-events: none;
      cursor: default;
    }

    #gridOverlay:active { cursor: default; }

    #buildingMarkers {
      position: fixed;
      inset: 0;
      z-index: 1;
      pointer-events: none;
    }

    #selectedPointMarker {
      position: fixed;
      width: 34px;
      height: 34px;
      display: none;
      transform: translate(-50%, -50%);
      border: 2px solid #f2c94c;
      border-radius: 50%;
      box-shadow: 0 0 0 3px rgba(242, 201, 76, 0.22),
        0 0 18px rgba(242, 201, 76, 0.52);
      pointer-events: none;
      z-index: 2;
    }

    .buildingMarker {
      position: absolute;
      width: 26px;
      height: 26px;
      display: grid;
      place-items: center;
      transform: translate(-50%, -50%);
      border: 1px solid rgba(230, 236, 242, 0.70);
      border-radius: 50%;
      background: rgba(7, 13, 22, 0.82);
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.55);
      font-size: 15px;
      line-height: 1;
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

    .topbar {
      position: fixed;
      top: 14px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: center;
      max-width: min(720px, calc(100vw - 220px));
      z-index: 2;
    }

    .sidebar {
      position: fixed;
      right: 14px;
      top: 58px;
      width: min(340px, calc(100vw - 28px));
      max-height: calc(100vh - 72px);
      overflow: auto;
      display: grid;
      gap: 8px;
      z-index: 2;
    }

    .panel {
      min-height: 34px;
      padding: 8px 10px;
      border: 1px solid rgba(230, 236, 242, 0.20);
      border-radius: 8px;
      background: rgba(7, 13, 22, 0.72);
      box-shadow: 0 8px 26px rgba(0, 0, 0, 0.55);
      backdrop-filter: blur(10px);
      font-size: 12px;
      line-height: 1.35;
      color: #e6ecf2;
      white-space: nowrap;
    }

    .panel h2 {
      margin: 0 0 6px;
      font-size: 12px;
      font-weight: 700;
      color: #f0f4f7;
    }

    .panel p {
      margin: 0;
      white-space: normal;
    }

    .compact {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .resourceGrid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 5px 10px;
      white-space: normal;
    }

    .resourceGrid span {
      min-width: 0;
    }

    .resourceTrend {
      display: inline-block;
      width: 1em;
      color: #9ba7b3;
      text-align: center;
    }

    .resourceTrend.up { color: #5bd17d; }

    .resourceTrend.down { color: #ff7b7b; }

    .statusLog {
      display: grid;
      gap: 4px;
      max-height: 112px;
      overflow: auto;
      white-space: normal;
      color: #cbd4dc;
    }

    .buildingList {
      display: grid;
      grid-template-columns: 1fr;
      gap: 6px;
    }

    .legendGrid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 5px 8px;
      white-space: normal;
    }

    .legendItem {
      display: flex;
      align-items: center;
      gap: 5px;
      min-width: 0;
    }

    .swatch {
      width: 10px;
      height: 10px;
      border-radius: 2px;
      flex: 0 0 auto;
      border: 1px solid rgba(230, 236, 242, 0.28);
    }

    details {
      margin-top: 6px;
      white-space: normal;
    }

    summary { cursor: pointer; }

    input {
      min-width: 90px;
      height: 28px;
      border: 1px solid rgba(230, 236, 242, 0.22);
      border-radius: 6px;
      background: rgba(7, 13, 22, 0.82);
      color: #e6ecf2;
      padding: 0 8px;
      font: 12px/1 ui-sans-serif, system-ui, sans-serif;
    }

    .help {
      white-space: normal;
      max-width: 280px;
      font-size: 11px;
      color: #b3bdc6;
    }

    .help kbd {
      display: inline-block;
      padding: 1px 5px;
      border: 1px solid rgba(230, 236, 242, 0.28);
      border-bottom-width: 2px;
      border-radius: 4px;
      background: rgba(15, 24, 38, 0.92);
      font: 600 10px ui-monospace, SFMono-Regular, Menlo, monospace;
      color: #e6ecf2;
      margin: 0 1px;
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
      border: 1px solid rgba(230, 236, 242, 0.22);
      border-radius: 8px;
      background: rgba(7, 13, 22, 0.78);
      color: #e6ecf2;
      font: 700 18px/1 ui-sans-serif, system-ui, sans-serif;
      box-shadow: 0 8px 26px rgba(0, 0, 0, 0.55);
      cursor: pointer;
      backdrop-filter: blur(10px);
    }

    .textButton {
      width: auto;
      min-width: 34px;
      padding: 0 9px;
      font-size: 12px;
    }

    .buildingList button {
      width: 100%;
      min-height: 32px;
      height: auto;
      padding: 7px 8px;
      text-align: left;
      font-size: 11px;
      line-height: 1.2;
    }

    .buildingList button.unavailable {
      color: rgba(230, 236, 242, 0.58);
      border-color: rgba(230, 236, 242, 0.14);
    }

    .buildingActions {
      display: flex;
      gap: 6px;
      margin-top: 8px;
    }

    .buildingActions button {
      min-width: 0;
      flex: 1 1 0;
      height: 30px;
      font-size: 11px;
      padding: 0 6px;
    }

    button:disabled {
      color: rgba(230, 236, 242, 0.42);
      cursor: not-allowed;
      background: rgba(7, 13, 22, 0.48);
    }

    button:hover { background: rgba(20, 36, 58, 0.92); }

    button:disabled:hover { background: rgba(7, 13, 22, 0.48); }

    .error {
      position: fixed;
      inset: auto 16px 16px 16px;
      padding: 12px 16px;
      border-radius: 10px;
      border: 1px solid rgba(220, 90, 90, 0.55);
      background: rgba(40, 12, 12, 0.85);
      color: #ffd7d7;
      font-size: 13px;
      display: none;
    }

    @media (max-width: 720px) {
      .topbar {
        top: 8px;
        left: 8px;
        right: 8px;
        transform: none;
        max-width: none;
        justify-content: flex-start;
      }

      .tools {
        display: none;
      }

      .hud {
        top: 154px;
        left: 8px;
        right: 8px;
        max-width: none;
        z-index: 2;
      }

      #stats,
      #lod,
      .hud .help {
        display: none;
      }

      .sidebar {
        left: 8px;
        right: 8px;
        top: 560px;
        width: auto;
        max-height: calc(100vh - 568px);
      }

      .panel {
        white-space: normal;
      }

      .resourceGrid,
      .buildingList,
      .legendGrid {
        grid-template-columns: 1fr;
      }

      .buildingList button {
        white-space: normal;
      }
    }
  </style>
</head>
<body>
  <canvas id="planet" tabindex="0"></canvas>
  <canvas id="gridOverlay" aria-hidden="true"></canvas>
  <div id="buildingMarkers" aria-hidden="true"></div>
  <div id="selectedPointMarker" aria-hidden="true"></div>
  <div class="hud" aria-live="polite">
    <div class="panel" id="stats"></div>
    <div class="panel" id="lod"></div>
    <div class="panel help">
      <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> rotate &middot;
      <kbd>Q</kbd><kbd>E</kbd> roll &middot;
      <kbd>+</kbd><kbd>-</kbd> zoom &middot;
      <kbd>R</kbd> reset
    </div>
    <div class="panel" id="resourcesPanel"></div>
    <div class="panel" id="demographicsPanel"></div>
    <div class="panel">
      <h2>Статус</h2>
      <div class="statusLog" id="statusLog"></div>
    </div>
  </div>
  <div class="topbar">
    <div class="panel compact">
      <input id="nicknameInput" value="Игрок1" aria-label="Nickname">
      <button class="textButton" id="loginButton" title="Login" aria-label="Login">OK</button>
    </div>
    <div class="panel compact" id="timePanel"></div>
    <button id="pauseButton" title="Pause or resume time" aria-label="Pause or resume time">▶</button>
    <button id="stepWeekButton" title="Advance one week" aria-label="Advance one week">↷</button>
    <button id="skipMonthButton" title="Skip one month" aria-label="Skip one month">M</button>
    <button id="skipYearButton" title="Skip one year" aria-label="Skip one year">Y</button>
    <button id="gridLayerButton" title="Toggle grid layer" aria-label="Toggle grid layer">⌗</button>
  </div>
  <div class="tools">
    <button id="zoomIn" title="Zoom in" aria-label="Zoom in">+</button>
    <button id="zoomOut" title="Zoom out" aria-label="Zoom out">-</button>
    <button id="reset" title="Reset camera" aria-label="Reset camera">R</button>
  </div>
  <aside class="sidebar">
    <div class="panel" id="selectedPointPanel"></div>
    <div class="panel">
      <h2>Постройки</h2>
      <div class="buildingList" id="buildingMenu"></div>
    </div>
    <div class="panel">
      <h2>Биомы</h2>
      <div class="legendGrid" id="biomeLegend"></div>
    </div>
  </aside>
  <div class="error" id="error"></div>

  <script>
    const payload = __SPHERE_PAYLOAD__;
    const canvas = document.getElementById("planet");
    const gridOverlay = document.getElementById("gridOverlay");
    const gridContext = gridOverlay.getContext("2d");
    const buildingMarkers = document.getElementById("buildingMarkers");
    const selectedPointMarker = document.getElementById("selectedPointMarker");
    const stats = document.getElementById("stats");
    const lodPanel = document.getElementById("lod");
    const errorPanel = document.getElementById("error");
    const nicknameInput = document.getElementById("nicknameInput");
    const timePanel = document.getElementById("timePanel");
    const pauseButton = document.getElementById("pauseButton");
    const resourcesPanel = document.getElementById("resourcesPanel");
    const demographicsPanel = document.getElementById("demographicsPanel");
    const selectedPointPanel = document.getElementById("selectedPointPanel");
    const buildingMenu = document.getElementById("buildingMenu");
    const biomeLegend = document.getElementById("biomeLegend");
    const statusLog = document.getElementById("statusLog");

    const ZOOM_MIN = 0.55;
    const ZOOM_MAX = 3.2;
    const KEY_ROTATE_STEP = 0.035;
    const POINTER_ROTATE_STEP = 0.0035;
    const KEY_ZOOM_STEP = 1.10;
    const WEEK_SECONDS = 5; // tick every 5 seconds
    const DAYS_PER_WEEK = 7;
    const WEEKS_PER_MONTH = 4;
    const MONTHS_PER_YEAR = 12;
    const BIRTH_WEEKS = 8 * WEEKS_PER_MONTH;
    const ADULT_WEEKS = 16 * WEEKS_PER_MONTH * MONTHS_PER_YEAR;
    const DAILY_FOOD_PER_PERSON = 0.002;
    const DAILY_WATER_PER_PERSON = 0.003;
    const FEATURE_RIVER = 1;
    const FEATURE_LAKE = 2;
    const FEATURE_MOUNTAIN = 4;
    const FEATURE_ISLAND = 8;
    const BUILDINGS = [
      { id: "city_center", label: "Центр города", icon: "◎", cost: {}, requires: [], vacancies: 0, capacity: 10, unique: true },
      { id: "warehouse", label: "Склад", icon: "▣", cost: { stone: 3, roundwood: 2 }, requires: ["city_center"], vacancies: 0 },
      { id: "pump", label: "Насос", icon: "↧", cost: { roundwood: 2 }, requires: ["city_center"], vacancies: 1 },
      { id: "farm", label: "Ферма", icon: "▦", cost: { clay: 2, roundwood: 1 }, requires: ["city_center"], vacancies: 2 },
      { id: "quarry", label: "Карьер", icon: "◫", cost: { stone: 4 }, requires: ["city_center"], vacancies: 3 },
      { id: "stone_quarry", label: "Каменоломня", icon: "▰", cost: { stone: 8, roundwood: 2 }, requires: ["city_center"], vacancies: 4 },
      { id: "lumberjack_site", label: "Лесозаготовка", icon: "♧", cost: { stone: 2, tools: 0.2 }, requires: ["stone_quarry"], vacancies: 4 },
      { id: "mine", label: "Шахта", icon: "▱", cost: { tools: 1, roundwood: 6 }, requires: ["city_center"], vacancies: 4, biome: "mountain", feature: FEATURE_MOUNTAIN },
      { id: "housing1", label: "Жильё1", cost: { clay: 5 }, requires: ["warehouse"], vacancies: 0, capacity: 5 },
      { id: "housing2", label: "Жильё2", cost: { roundwood: 12 }, requires: ["lumberjack_site"], vacancies: 0, capacity: 25 },
      { id: "housing3", label: "Жильё3", cost: { plank: 28 }, requires: ["sawmill"], vacancies: 0, capacity: 100 },
      { id: "housing4", label: "Жильё4", cost: { brick: 120 }, requires: ["brick_factory"], vacancies: 0, capacity: 500 },
      { id: "housing5", label: "Жильё5", cost: { concrete: 1100, metal: 120 }, requires: ["foundry"], vacancies: 0, capacity: 5000 },
      { id: "brick_factory", label: "Кирпичный завод", icon: "▤", cost: { stone: 12, roundwood: 4 }, requires: ["quarry"], vacancies: 6 },
      { id: "forge", label: "Кузня", cost: { stone: 18, roundwood: 6 }, requires: ["stone_quarry"], vacancies: 4 },
      { id: "sawmill", label: "Лесопилка", cost: { stone: 8, roundwood: 8 }, requires: ["lumberjack_site"], vacancies: 4 },
      { id: "foundry", label: "Литейный завод", cost: { stone: 20, brick: 10 }, requires: ["forge"], vacancies: 8 },
      { id: "concrete_factory", label: "Бетонный завод", icon: "▧", cost: { brick: 12, stone: 10 }, requires: ["brick_factory"], vacancies: 6 },
      { id: "boiler_house", label: "Котельная", icon: "◈", cost: { stone: 6, roundwood: 4 }, requires: ["city_center"], vacancies: 2 },
    ];
    const gameState = {
      nickname: "Игрок1",
      paused: true,
      day: 0,
      birthProgressWeeks: 0,
      selectedPoint: null,
      layers: { grid: false },
      resourceTrends: {},
      resources: {
        food: 6.72,
        water: 10.08,
        roundwood: 80,
        stone: 80,
        sand: 30,
        clay: 40,
        raw_metal: 12,
        tools: 2,
        coal: 8,
        energy_mw_day: 0,
      },
      people: {
        adults: 10,
        children: 0,
        adultNames: ["Чел1", "Чел2", "Чел3", "Чел4", "Чел5", "Чел6", "Чел7", "Чел8", "Чел9", "Чел10"],
        childrenAgeWeeks: [],
        nextId: 11,
      },
      buildings: [],
      status: ["Игрок Игрок1 вошёл в игру: выберите точку для центра города."],
    };

    let rotationX = -0.28;
    let rotationY = 0.54;
    let rotationZ = 0.0;
    let zoom = 1.0;
    let dragging = false;
    let pointerX = 0;
    let pointerY = 0;
    const pressedKeys = new Set();
    let keyAnimationHandle = null;
    let lastKeyTimestamp = 0;
    let movedDuringDrag = false;
    let currentViewProjection = null;

    function showError(message) {
      errorPanel.textContent = message;
      errorPanel.style.display = "block";
    }

    const gl = canvas.getContext("webgl2", { antialias: true, alpha: false });
    if (!gl) {
      showError("WebGL2 is not available in this browser; v0.0.4 viewer needs WebGL2.");
      throw new Error("WebGL2 unavailable");
    }

    const VERTEX_SHADER = `#version 300 es
      precision highp float;
      layout(location = 0) in vec3 aPosition;
      layout(location = 1) in float aBiome;
      layout(location = 2) in float aElevation;
      layout(location = 3) in float aFeature;
      uniform mat4 uViewProjection;
      uniform mat4 uViewMatrix;
      uniform float uPointScale;
      uniform float uPlanetRadius;
      out vec3 vColor;
      out vec3 vNormal;
      out float vFacing;

      vec3 biomeColor(float index) {
        int i = int(index + 0.5);
        if (i == 0) return vec3(0.184, 0.435, 0.604);
        if (i == 1) return vec3(0.184, 0.561, 0.718);
        if (i == 2) return vec3(0.902, 0.945, 0.953);
        if (i == 3) return vec3(0.654, 0.722, 0.627);
        if (i == 4) return vec3(0.275, 0.451, 0.310);
        if (i == 5) return vec3(0.455, 0.639, 0.353);
        if (i == 6) return vec3(0.761, 0.694, 0.361);
        if (i == 7) return vec3(0.824, 0.604, 0.302);
        if (i == 8) return vec3(0.153, 0.565, 0.357);
        if (i == 9) return vec3(0.561, 0.584, 0.553);
        return vec3(0.7, 0.7, 0.7);
      }

      bool hasFeature(float flags, float bit) {
        return mod(floor(flags / bit), 2.0) >= 1.0;
      }

      void main() {
        float radiusFactor = 1.0 + clamp(aElevation, -200.0, 3000.0) / 90000.0;
        vec3 worldPos = aPosition * uPlanetRadius * radiusFactor;
        gl_Position = uViewProjection * vec4(worldPos, 1.0);
        gl_PointSize = max(1.0, uPointScale / max(gl_Position.w, 0.0001));
        vec3 viewNormal = normalize((uViewMatrix * vec4(aPosition, 0.0)).xyz);
        vFacing = viewNormal.z;
        vColor = biomeColor(aBiome);
        if (hasFeature(aFeature, 1.0)) vColor = mix(vColor, vec3(0.170, 0.720, 0.930), 0.72);
        if (hasFeature(aFeature, 2.0)) vColor = vec3(0.180, 0.560, 0.720);
        if (hasFeature(aFeature, 4.0)) vColor = mix(vColor, vec3(0.760, 0.760, 0.720), 0.48);
        vNormal = viewNormal;
      }
    `;

    const FRAGMENT_SHADER = `#version 300 es
      precision highp float;
      in vec3 vColor;
      in vec3 vNormal;
      in float vFacing;
      out vec4 fragColor;
      uniform vec3 uLight;

      void main() {
        if (vFacing <= 0.0) discard;
        vec2 offset = gl_PointCoord - vec2(0.5);
        float distance = dot(offset, offset);
        if (distance > 0.25) discard;
        float diffuse = clamp(dot(normalize(vNormal), uLight) * 0.7 + 0.65, 0.0, 1.2);
        float alpha = smoothstep(0.25, 0.05, distance);
        fragColor = vec4(vColor * diffuse, alpha);
      }
    `;

    function compile(type, source) {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        const info = gl.getShaderInfoLog(shader);
        gl.deleteShader(shader);
        showError("Shader compile failed: " + info);
        throw new Error(info);
      }
      return shader;
    }

    const program = gl.createProgram();
    gl.attachShader(program, compile(gl.VERTEX_SHADER, VERTEX_SHADER));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, FRAGMENT_SHADER));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      showError("Program link failed: " + gl.getProgramInfoLog(program));
      throw new Error("Program link failed");
    }
    gl.useProgram(program);

    const uViewProjection = gl.getUniformLocation(program, "uViewProjection");
    const uViewMatrix = gl.getUniformLocation(program, "uViewMatrix");
    const uPointScale = gl.getUniformLocation(program, "uPointScale");
    const uPlanetRadius = gl.getUniformLocation(program, "uPlanetRadius");
    const uLight = gl.getUniformLocation(program, "uLight");

    const planetRadiusUnit = 1.0;
    gl.uniform1f(uPlanetRadius, planetRadiusUnit);
    gl.uniform3f(uLight, -0.45, -0.52, 0.72);

    const levels = (payload.levels || []).map((level) => buildLevel(level));
    if (!levels.length) {
      showError("Payload contains no LOD levels.");
      throw new Error("empty payload");
    }
    const zoomThresholds = payload.zoomThresholds || [];
    let activeIndex = pickLevel(zoom);

    function buildLevel(level) {
      const vao = gl.createVertexArray();
      gl.bindVertexArray(vao);

      const positions = new Float32Array(level.positions);
      const biomes = new Uint8Array(level.biomes);
      const elevations = new Int16Array(level.elevations);
      const features = new Uint8Array(level.features || new Array(level.count).fill(0));

      const positionBuffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);

      const biomeBuffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, biomeBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, biomes, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(1);
      gl.vertexAttribPointer(1, 1, gl.UNSIGNED_BYTE, false, 0, 0);

      const elevationBuffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, elevationBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, elevations, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(2);
      gl.vertexAttribPointer(2, 1, gl.SHORT, false, 0, 0);

      const featureBuffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, featureBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, features, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(3);
      gl.vertexAttribPointer(3, 1, gl.UNSIGNED_BYTE, false, 0, 0);

      gl.bindVertexArray(null);
      return { vao, count: level.count, positions, biomes, elevations, features };
    }

    function pickLevel(currentZoom) {
      let index = 0;
      for (let i = 0; i < zoomThresholds.length; i += 1) {
        if (currentZoom >= zoomThresholds[i]) {
          index = i + 1;
        }
      }
      return Math.min(index, levels.length - 1);
    }

    function updateStats() {
      const level = payload.levels[activeIndex];
      const target = payload.targetLogicalCount.toLocaleString("en-US");
      const rendered = level.count.toLocaleString("en-US");
      stats.textContent =
        `WebGL2 | zoom ${zoom.toFixed(2)}x | rendered ${rendered} pts | logical ${target}`;
      lodPanel.textContent =
        `LOD ${activeIndex + 1}/${levels.length} (LOD switching at zoom thresholds)`;
    }

    function calendarLabel(day) {
      const weekIndex = Math.floor(day / DAYS_PER_WEEK);
      const week = weekIndex % WEEKS_PER_MONTH + 1;
      const absoluteWeek = weekIndex + 1;
      const month = Math.floor(weekIndex / WEEKS_PER_MONTH) % MONTHS_PER_YEAR + 1;
      const year = Math.floor(weekIndex / (WEEKS_PER_MONTH * MONTHS_PER_YEAR)) + 1;
      return `Неделя ${week} (${absoluteWeek}) / Месяц ${month} / Год ${year}`;
    }

    function resourceLabel(name) {
      return {
        food: "еда",
        water: "вода",
        roundwood: "брёвна",
        stone: "камень",
        sand: "песок",
        clay: "глина",
        raw_metal: "сырая руда",
        tools: "инструменты",
        coal: "уголь",
        energy_mw_day: "энергия",
        plank: "доски",
        brick: "кирпич",
        metal: "металл",
        concrete: "бетон",
      }[name] || name;
    }

    function resourceUnit(name) {
      if (name === "energy_mw_day") return "МВт·сут";
      return "т";
    }

    function formatCost(cost) {
      const parts = Object.entries(cost || {}).map(([name, amount]) =>
        `${resourceLabel(name)} ${amount} ${resourceUnit(name)}`,
      );
      return parts.length ? parts.join(", ") : "без затрат";
    }

    function buildingDefinition(id) {
      return BUILDINGS.find((item) => item.id === id) || null;
    }

    function buildingIcon(id) {
      const definition = buildingDefinition(id);
      return definition && definition.icon ? definition.icon : "□";
    }

    function buildingLabel(id) {
      const definition = buildingDefinition(id);
      return definition ? definition.label : id;
    }

    function hasBuilding(id) {
      return gameState.buildings.some((building) => building.id === id);
    }

    function hasActiveBuilding(id) {
      return gameState.buildings.some((building) => building.id === id && building.active !== false);
    }

    function buildingAtPoint(pointId) {
      return gameState.buildings.find((building) => building.pointId === pointId) || null;
    }

    function canAfford(cost) {
      return Object.entries(cost || {}).every(([name, amount]) =>
        (gameState.resources[name] || 0) >= amount,
      );
    }

    function currentDemographics() {
      const vacancies = gameState.buildings.reduce((total, building) => {
        if (building.active === false) return total;
        const definition = buildingDefinition(building.id);
        return total + (definition ? definition.vacancies || 0 : 0);
      }, 0);
      const adults = gameState.people.adultNames.length;
      const children = gameState.people.childrenAgeWeeks.length;
      gameState.people.adults = adults;
      gameState.people.children = children;
      return {
        adults,
        children,
        vacancies,
        unemployed: Math.max(0, adults - vacancies),
      };
    }

    function housingCapacity() {
      return gameState.buildings.reduce((total, building) => {
        if (building.active === false) return total;
        const definition = buildingDefinition(building.id);
        return total + (definition ? definition.capacity || 0 : 0);
      }, 0);
    }

    function pushStatus(message) {
      gameState.status.unshift(message);
      renderGameUi();
    }

    function resourceTrend(name) {
      const delta = gameState.resourceTrends[name] || 0;
      if (delta > 0.000001) return { symbol: "↑", className: "up" };
      if (delta < -0.000001) return { symbol: "↓", className: "down" };
      return { symbol: "·", className: "" };
    }

    function biomeName(index) {
      const biome = (payload.biomes || [])[index];
      return biome ? biome.name : "unknown";
    }

    function biomeLabel(name) {
      return {
        ocean: "океан",
        lake: "озеро",
        polar: "полярный",
        tundra: "тундра",
        boreal: "тайга",
        temperate: "умеренный",
        steppe: "степь",
        desert: "пустыня",
        tropical: "тропики",
        mountain: "горы",
      }[name] || name;
    }

    function latLonForVector(x, y, z) {
      const latitude = Math.asin(Math.max(-1, Math.min(1, z))) * 180 / Math.PI;
      const longitude = Math.atan2(y, x) * 180 / Math.PI;
      return { latitude, longitude };
    }

    function climateSummaryForLatitude(latitude) {
      const months = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"];
      const absLatitude = Math.abs(latitude);
      return months.map((month, index) => {
        const yearFraction = index / 12;
        const seasonal = Math.sin(2 * Math.PI * (yearFraction - 0.25));
        const hemisphereSeason = latitude >= 0 ? seasonal : -seasonal;
        const base = 24 - absLatitude * 0.42;
        const amplitude = 4 + absLatitude * 0.18;
        const temperature = base + amplitude * hemisphereSeason;
        const rainfall = absLatitude < 20 ? 90 : absLatitude < 55 ? 55 : 24;
        return `${month}: ${temperature.toFixed(0)}°C, ${rainfall} мм`;
      }).join("<br>");
    }

    function renderBiomeLegend() {
      biomeLegend.innerHTML = (payload.biomes || []).map((biome) =>
        `<span class="legendItem"><span class="swatch" style="background:${biome.color}"></span>${biomeLabel(biome.name)}</span>`
      ).join("");
    }

    function renderGameUi() {
      const demographics = currentDemographics();
      const dateLabel = calendarLabel(gameState.day);
      timePanel.textContent = gameState.paused
        ? `Пауза | ${dateLabel} | планирование доступно`
        : `Время идёт | ${dateLabel} | тик 1 неделя / ${WEEK_SECONDS} c`;
      pauseButton.textContent = gameState.paused ? "▶" : "Ⅱ";

      const resourceEntries = Object.entries(gameState.resources)
        .filter(([, amount]) => amount > 0.000001)
        .slice(0, 12)
        .map(([name, amount]) => {
          const trend = resourceTrend(name);
          return `<span><span class="resourceTrend ${trend.className}">${trend.symbol}</span> ${resourceLabel(name)} ${amount.toFixed(3)} ${resourceUnit(name)}</span>`;
        })
        .join("");
      resourcesPanel.innerHTML = `<h2>Склад</h2><div class="resourceGrid">${resourceEntries}</div>`;
      demographicsPanel.innerHTML =
        `<h2>Демография</h2>` +
        `<p>взрослые ${demographics.adults} · дети ${demographics.children} · ` +
        `безработные ${demographics.unemployed} · вакансии ${demographics.vacancies} · ` +
        `жильё ${housingCapacity()}</p>`;

      if (gameState.selectedPoint === null) {
        selectedPointPanel.innerHTML =
          activeIndex === levels.length - 1
            ? `<h2>Точка</h2><p>Выберите точку на планете.</p>`
            : `<h2>Точка</h2><p>Выбор активен только на максимальном LOD.</p>`;
      } else {
        const point = gameState.selectedPoint;
        const flags = point.features;
        const existingBuilding = buildingAtPoint(point.id);
        const featureNames = [];
        if (flags & FEATURE_RIVER) featureNames.push("река");
        if (flags & FEATURE_LAKE) featureNames.push("озеро");
        if (flags & FEATURE_MOUNTAIN) featureNames.push("горы");
        if (flags & FEATURE_ISLAND) featureNames.push("редкий остров");
        selectedPointPanel.innerHTML =
          `<h2>Точка #${point.id}</h2>` +
          `<p>LOD ${activeIndex + 1}, ${biomeLabel(point.biome)}, высота ${point.elevation} м` +
          `${featureNames.length ? `, ${featureNames.join(", ")}` : ""}</p>` +
          `<p>широта ${point.latitude.toFixed(1)}°, долгота ${point.longitude.toFixed(1)}°</p>` +
          `<p>постройка: ${
            existingBuilding
              ? `${buildingIcon(existingBuilding.id)} ${buildingLabel(existingBuilding.id)} (${existingBuilding.active === false ? "выключена" : "активна"})`
              : "нет"
          }</p>` +
          (
            existingBuilding
              ? `<p>работник: ${existingBuilding.workerName || "нет"}</p>` +
                `<div class="buildingActions">` +
                `<button type="button" data-building-action="toggle">${existingBuilding.active === false ? "Активировать" : "Выключить"}</button>` +
                `<button type="button" data-building-action="demolish">Снести</button>` +
                `</div>`
              : ""
          ) +
          `<details><summary>Климат года</summary>${climateSummaryForLatitude(point.latitude)}</details>`;
      }

      buildingMenu.innerHTML = "";
      for (const building of BUILDINGS) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = `${building.icon || "□"} ${building.label} · ${formatCost(building.cost)}`;
        const reason = buildingUnavailableReason(building);
        if (reason) {
          button.className = "unavailable";
          button.title = reason;
        }
        button.addEventListener("click", () => {
          const currentReason = buildingUnavailableReason(building);
          if (currentReason) {
            showUnavailablePopup(currentReason);
            return;
          }
          planBuilding(building);
        });
        buildingMenu.appendChild(button);
      }

      const recentStatus = gameState.status.slice(0, 8)
        .map((item) => `<div>${item}</div>`)
        .join("");
      const fullStatus = gameState.status
        .map((item) => `<div>${item}</div>`)
        .join("");
      statusLog.innerHTML =
        recentStatus +
        `<details><summary>Вся хронология (${gameState.status.length})</summary>${fullStatus}</details>`;
    }

    function canPlaceOnSelectedPoint(building) {
      if (gameState.selectedPoint === null) return false;
      if (gameState.selectedPoint.biome === "ocean") return false;
      if (buildingAtPoint(gameState.selectedPoint.id)) return false;
      if (building.biome && gameState.selectedPoint.biome !== building.biome) return false;
      if (building.feature && (gameState.selectedPoint.features & building.feature) !== building.feature) return false;
      return true;
    }

    function missingCostParts(cost) {
      return Object.entries(cost || {})
        .filter(([name, amount]) => (gameState.resources[name] || 0) + 1e-9 < amount)
        .map(([name, amount]) => `${resourceLabel(name)} ${amount} ${resourceUnit(name)}`);
    }

    function buildingUnavailableReason(building) {
      if (building.unique && hasBuilding(building.id)) {
        return `${building.label} уже построен.`;
      }
      const missingRequirements = building.requires.filter((required) => !hasActiveBuilding(required));
      if (missingRequirements.length) {
        return `Нужна постройка: ${missingRequirements.map(buildingLabel).join(", ")}.`;
      }
      if (gameState.selectedPoint === null) {
        return "Сначала выберите точку на максимальном LOD.";
      }
      if (gameState.selectedPoint.biome === "ocean") {
        return "В биоме океана нельзя ничего строить.";
      }
      if (buildingAtPoint(gameState.selectedPoint.id)) {
        return `Точка #${gameState.selectedPoint.id} уже занята.`;
      }
      if (building.biome && gameState.selectedPoint.biome !== building.biome) {
        return `${building.label} можно строить только в биоме: ${biomeLabel(building.biome)}.`;
      }
      if (building.feature && (gameState.selectedPoint.features & building.feature) !== building.feature) {
        return `${building.label} требует подходящую особенность точки.`;
      }
      const missing = missingCostParts(building.cost);
      if (missing.length) {
        return `Не хватает ресурсов: ${missing.join(", ")}.`;
      }
      return "";
    }

    function showUnavailablePopup(message) {
      alert(message);
      pushStatus(message);
    }

    function planBuilding(building) {
      const reason = buildingUnavailableReason(building);
      if (reason) {
        showUnavailablePopup(reason);
        return;
      }
      for (const [name, amount] of Object.entries(building.cost || {})) {
        gameState.resources[name] = Math.max(0, (gameState.resources[name] || 0) - amount);
      }
      gameState.buildings.push({
        id: building.id,
        pointId: gameState.selectedPoint.id,
        relation: "own",
        active: true,
        workerName: null,
      });
      pushStatus(`${gameState.nickname}: ${building.label} запланирована в точке #${gameState.selectedPoint.id}.`);
      renderSelectedPointMarker();
      draw();
    }

    function buildingAtSelectedPoint() {
      if (gameState.selectedPoint === null) return null;
      return buildingAtPoint(gameState.selectedPoint.id);
    }

    function toggleSelectedBuilding() {
      const building = buildingAtSelectedPoint();
      if (!building) return;
      building.active = building.active === false;
      building.workerName = null;
      pushStatus(`${buildingLabel(building.id)} ${building.active ? "активирована" : "деактивирована"}.`);
      draw();
    }

    function demolishSelectedBuilding() {
      const building = buildingAtSelectedPoint();
      if (!building) return;
      gameState.buildings = gameState.buildings.filter((item) => item !== building);
      pushStatus(`${buildingLabel(building.id)} снесена в точке #${building.pointId}.`);
      draw();
    }

    function resourceSnapshot() {
      return Object.fromEntries(
        Object.entries(gameState.resources).map(([name, amount]) => [name, amount || 0]),
      );
    }

    function updateResourceTrends(previous) {
      const names = new Set([...Object.keys(previous), ...Object.keys(gameState.resources)]);
      gameState.resourceTrends = {};
      for (const name of names) {
        gameState.resourceTrends[name] = (gameState.resources[name] || 0) - (previous[name] || 0);
      }
    }

    function addResource(name, amount) {
      gameState.resources[name] = (gameState.resources[name] || 0) + amount;
    }

    function takeResources(cost) {
      if (!canAfford(cost)) return false;
      for (const [name, amount] of Object.entries(cost || {})) {
        gameState.resources[name] = Math.max(0, (gameState.resources[name] || 0) - amount);
      }
      return true;
    }

    function staffBuilding(building, availableWorkers) {
      const definition = buildingDefinition(building.id);
      const needed = Math.max(1, definition ? definition.vacancies || 1 : 1);
      building.workerName = null;
      if (building.active === false) return false;
      if (availableWorkers.length < needed) return false;
      const assigned = availableWorkers.splice(0, needed);
      building.workerName = assigned.join(", ");
      return true;
    }

    function consumeWeeklyNeeds() {
      const adultFood = DAILY_FOOD_PER_PERSON * DAYS_PER_WEEK;
      const adultWater = DAILY_WATER_PER_PERSON * DAYS_PER_WEEK;
      let deaths = 0;
      const adultSurvivors = [];
      const childSurvivors = [];

      for (const name of gameState.people.adultNames) {
        if ((gameState.resources.food || 0) + 1e-9 >= adultFood && (gameState.resources.water || 0) + 1e-9 >= adultWater) {
          gameState.resources.food -= adultFood;
          gameState.resources.water -= adultWater;
          adultSurvivors.push(name);
        } else {
          deaths += 1;
        }
      }

      for (const child of gameState.people.childrenAgeWeeks) {
        const childFood = adultFood * 0.5;
        const childWater = adultWater * 0.5;
        if ((gameState.resources.food || 0) + 1e-9 >= childFood && (gameState.resources.water || 0) + 1e-9 >= childWater) {
          gameState.resources.food -= childFood;
          gameState.resources.water -= childWater;
          childSurvivors.push(child);
        } else {
          deaths += 1;
        }
      }

      gameState.people.adultNames = adultSurvivors;
      gameState.people.childrenAgeWeeks = childSurvivors;
      gameState.people.adults = adultSurvivors.length;
      gameState.people.children = childSurvivors.length;
      return deaths;
    }

    function runBuildingProduction() {
      const availableWorkers = gameState.people.adultNames.slice();
      for (const building of gameState.buildings) {
        building.workerName = null;
        if (!["pump", "farm", "quarry", "stone_quarry", "lumberjack_site", "mine", "brick_factory", "forge", "concrete_factory", "boiler_house"].includes(building.id)) {
          continue;
        }
        if (!staffBuilding(building, availableWorkers)) continue;
        if (building.id === "pump") {
          addResource("water", 0.08 * DAYS_PER_WEEK);
        }
        if (building.id === "farm") {
          addResource("food", 0.06 * DAYS_PER_WEEK);
        }
        if (building.id === "quarry") {
          addResource("stone", 14);
          addResource("sand", 7);
          addResource("clay", 7);
        }
        if (building.id === "stone_quarry") {
          addResource("stone", 28);
        }
        if (building.id === "lumberjack_site") {
          addResource("roundwood", 28);
        }
        if (building.id === "mine") {
          addResource("raw_metal", 5.6);
        }
        if (building.id === "brick_factory" && takeResources({ clay: 14 })) {
          addResource("brick", 11.2);
        }
        if (building.id === "forge" && takeResources({ raw_metal: 10.5, roundwood: 3.5 })) {
          addResource("tools", 7);
        }
        if (building.id === "concrete_factory" && takeResources({ sand: 14, raw_metal: 7 })) {
          addResource("concrete", 8.4);
        }
        if (building.id === "boiler_house" && takeResources({ roundwood: 7 })) {
          addResource("energy_mw_day", 0.28);
        }
      }
    }

    function advanceChildrenAges() {
      const remainingChildren = [];
      const adultMessages = [];
      for (const child of gameState.people.childrenAgeWeeks) {
        child.ageWeeks += 1;
        if (child.ageWeeks >= ADULT_WEEKS) {
          gameState.people.adultNames.push(child.name);
          adultMessages.push(`${child.name} взрослеет.`);
        } else {
          remainingChildren.push(child);
        }
      }
      gameState.people.childrenAgeWeeks = remainingChildren;
      gameState.people.adults = gameState.people.adultNames.length;
      gameState.people.children = remainingChildren.length;
      return adultMessages;
    }

    function advanceBirths() {
      const peopleAfter = gameState.people.adultNames.length + gameState.people.childrenAgeWeeks.length;
      if (peopleAfter >= housingCapacity()) return [];
      gameState.birthProgressWeeks += Math.floor(gameState.people.adultNames.length / 2);
      const births = Math.floor(gameState.birthProgressWeeks / BIRTH_WEEKS);
      if (births <= 0) return [];
      const room = housingCapacity() - peopleAfter;
      const actualBirths = Math.min(room, births);
      const messages = [];
      for (let index = 0; index < actualBirths; index += 1) {
        const name = `Чел${gameState.people.nextId}`;
        gameState.people.nextId += 1;
        gameState.people.childrenAgeWeeks.push({ name, ageWeeks: 0 });
        messages.push(`${name} родился.`);
      }
      gameState.birthProgressWeeks -= actualBirths * BIRTH_WEEKS;
      gameState.people.children = gameState.people.childrenAgeWeeks.length;
      return messages;
    }

    function advanceWeek(options = {}) {
      gameState.day += 7;
      const previousResources = resourceSnapshot();
      const deaths = consumeWeeklyNeeds();
      runBuildingProduction();
      const adultMessages = advanceChildrenAges();
      const birthMessages = deaths > 0 ? [] : advanceBirths();
      updateResourceTrends(previousResources);

      const weekNumber = Math.floor(gameState.day / DAYS_PER_WEEK);
      if (deaths > 0) {
        pushStatus(`Неделя ${weekNumber}: ${deaths} жителей умерли от нехватки воды или еды.`);
        return;
      }
      for (const message of adultMessages) pushStatus(message);
      for (const message of birthMessages) pushStatus(message);
      if (!options.quiet) {
        pushStatus(`Неделя ${weekNumber}: склад обновлён, время можно поставить на паузу.`);
      } else {
        renderGameUi();
      }
    }

    function resourceRiskForWeeks(weeks) {
      const adultNeeds = gameState.people.adultNames.length * weeks;
      const childNeeds = gameState.people.childrenAgeWeeks.length * weeks * 0.5;
      const projectedFood = (adultNeeds + childNeeds) * DAILY_FOOD_PER_PERSON * DAYS_PER_WEEK;
      const projectedWater = (adultNeeds + childNeeds) * DAILY_WATER_PER_PERSON * DAYS_PER_WEEK;
      const risks = [];
      if ((gameState.resources.food || 0) + 1e-9 < projectedFood) risks.push("еды");
      if ((gameState.resources.water || 0) + 1e-9 < projectedWater) risks.push("воды");
      return risks.length ? `Есть риск нехватки ${risks.join(" и ")} при пропуске времени.` : "";
    }

    function advancePeriod(weeks, label) {
      const risk = resourceRiskForWeeks(weeks);
      if (risk && !window.confirm(`${risk} Продолжить?`)) {
        pushStatus(`${label}: пропуск отменён.`);
        return;
      }
      for (let index = 0; index < weeks; index += 1) {
        advanceWeek({ quiet: true });
      }
      pushStatus(`${label}: пропущено ${weeks} недель с сохранением недельных вычислений.`);
    }

    function buildPerspective(aspect) {
      const fov = (45 * Math.PI) / 180;
      const near = 0.05;
      const far = 50.0;
      const f = 1.0 / Math.tan(fov / 2);
      const out = new Float32Array(16);
      out[0] = f / aspect;
      out[5] = f;
      out[10] = (far + near) / (near - far);
      out[11] = -1;
      out[14] = (2 * far * near) / (near - far);
      return out;
    }

    function multiply(a, b) {
      const out = new Float32Array(16);
      for (let row = 0; row < 4; row += 1) {
        for (let col = 0; col < 4; col += 1) {
          let value = 0;
          for (let k = 0; k < 4; k += 1) {
            value += a[k * 4 + row] * b[col * 4 + k];
          }
          out[col * 4 + row] = value;
        }
      }
      return out;
    }

    function rotationMatrix() {
      const sx = Math.sin(rotationX), cx = Math.cos(rotationX);
      const sy = Math.sin(rotationY), cy = Math.cos(rotationY);
      const sz = Math.sin(rotationZ), cz = Math.cos(rotationZ);

      const rotX = new Float32Array([
        1, 0, 0, 0,
        0, cx, sx, 0,
        0, -sx, cx, 0,
        0, 0, 0, 1,
      ]);
      const rotY = new Float32Array([
        cy, 0, -sy, 0,
        0, 1, 0, 0,
        sy, 0, cy, 0,
        0, 0, 0, 1,
      ]);
      const rotZ = new Float32Array([
        cz, sz, 0, 0,
        -sz, cz, 0, 0,
        0, 0, 1, 0,
        0, 0, 0, 1,
      ]);
      return multiply(rotZ, multiply(rotX, rotY));
    }

    function viewMatrix() {
      const distance = 3.5 / zoom;
      const translate = new Float32Array([
        1, 0, 0, 0,
        0, 1, 0, 0,
        0, 0, 1, 0,
        0, 0, -distance, 1,
      ]);
      return multiply(translate, rotationMatrix());
    }

    function draw() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.floor(canvas.clientWidth * dpr);
      const height = Math.floor(canvas.clientHeight * dpr);
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(0.02, 0.04, 0.08, 1);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST);
      gl.depthFunc(gl.LEQUAL);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

      const aspect = canvas.width / Math.max(1, canvas.height);
      const projection = buildPerspective(aspect);
      const view = viewMatrix();
      const viewProjection = multiply(projection, view);
      currentViewProjection = viewProjection;
      gl.uniformMatrix4fv(uViewProjection, false, viewProjection);
      gl.uniformMatrix4fv(uViewMatrix, false, view);

      const level = levels[activeIndex];
      const densityFactor = Math.sqrt(20000 / Math.max(1, level.count));
      const baseScale = Math.min(canvas.width, canvas.height) * 0.012 * densityFactor;
      const pointScale = baseScale * Math.pow(zoom, 0.6);
      gl.uniform1f(uPointScale, pointScale);

      gl.bindVertexArray(level.vao);
      gl.drawArrays(gl.POINTS, 0, level.count);
      gl.bindVertexArray(null);
      drawGridLayer();
      renderBuildingMarkers();
      renderSelectedPointMarker();
    }

    function projectPoint(matrix, x, y, z) {
      const clipX = matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12];
      const clipY = matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13];
      const clipZ = matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14];
      const clipW = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15];
      if (clipW <= 0 || clipZ < -clipW || clipZ > clipW) return null;
      return {
        x: (clipX / clipW * 0.5 + 0.5) * canvas.clientWidth,
        y: (-clipY / clipW * 0.5 + 0.5) * canvas.clientHeight,
      };
    }

    function frontFacingPoint(x, y, z) {
      const matrix = rotationMatrix();
      const viewZ = matrix[2] * x + matrix[6] * y + matrix[10] * z;
      return viewZ > 0.0;
    }

    function spherePoint(latitude, longitude) {
      const lat = latitude * Math.PI / 180;
      const lon = longitude * Math.PI / 180;
      const cosLat = Math.cos(lat);
      return {
        x: cosLat * Math.cos(lon),
        y: cosLat * Math.sin(lon),
        z: Math.sin(lat),
      };
    }

    function resizeOverlayCanvas() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.floor(gridOverlay.clientWidth * dpr);
      const height = Math.floor(gridOverlay.clientHeight * dpr);
      if (gridOverlay.width !== width || gridOverlay.height !== height) {
        gridOverlay.width = width;
        gridOverlay.height = height;
      }
      gridContext.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function drawProjectedPolyline(points) {
      let drawing = false;
      for (const point of points) {
        const visible = frontFacingPoint(point.x, point.y, point.z);
        const projected = visible
          ? projectPoint(currentViewProjection, point.x, point.y, point.z)
          : null;
        if (!projected) {
          drawing = false;
          continue;
        }
        if (!drawing) {
          gridContext.moveTo(projected.x, projected.y);
          drawing = true;
        } else {
          gridContext.lineTo(projected.x, projected.y);
        }
      }
    }

    function drawGridLayer() {
      resizeOverlayCanvas();
      gridContext.clearRect(0, 0, gridOverlay.clientWidth, gridOverlay.clientHeight);
      if (!gameState.layers.grid || !currentViewProjection) return;
      gridContext.save();
      gridContext.strokeStyle = "rgba(230, 236, 242, 0.36)";
      gridContext.lineWidth = 1;
      gridContext.beginPath();
      for (let latitude = -60; latitude <= 60; latitude += 30) {
        const points = [];
        for (let longitude = -180; longitude <= 180; longitude += 4) {
          points.push(spherePoint(latitude, longitude));
        }
        drawProjectedPolyline(points);
      }
      for (let longitude = -150; longitude <= 180; longitude += 30) {
        const points = [];
        for (let latitude = -88; latitude <= 88; latitude += 4) {
          points.push(spherePoint(latitude, longitude));
        }
        drawProjectedPolyline(points);
      }
      gridContext.stroke();
      gridContext.restore();
    }

    function maxLevel() {
      return levels[levels.length - 1];
    }

    function pointVectorForId(pointId) {
      const level = maxLevel();
      if (pointId === null || pointId < 0 || pointId >= level.count) return null;
      const offset = pointId * 3;
      return {
        x: level.positions[offset],
        y: level.positions[offset + 1],
        z: level.positions[offset + 2],
      };
    }

    function selectPointById(pointId) {
      const level = maxLevel();
      if (pointId === null || pointId < 0 || pointId >= level.count) return false;
      const offset = pointId * 3;
      const latitudeLongitude = latLonForVector(
        level.positions[offset],
        level.positions[offset + 1],
        level.positions[offset + 2],
      );
      gameState.selectedPoint = {
        id: pointId,
        elevation: level.elevations[pointId],
        features: level.features[pointId],
        biome: biomeName(level.biomes[pointId]),
        latitude: latitudeLongitude.latitude,
        longitude: latitudeLongitude.longitude,
      };
      return true;
    }

    function renderBuildingMarkers() {
      buildingMarkers.innerHTML = "";
      if (!currentViewProjection) return;
      for (const building of gameState.buildings) {
        const point = pointVectorForId(building.pointId);
        if (!point || !frontFacingPoint(point.x, point.y, point.z)) continue;
        const projected = projectPoint(currentViewProjection, point.x, point.y, point.z);
        if (!projected) continue;
        const marker = document.createElement("span");
        marker.className = "buildingMarker";
        marker.textContent = buildingIcon(building.id);
        marker.title = buildingLabel(building.id);
        marker.style.left = `${projected.x}px`;
        marker.style.top = `${projected.y}px`;
        buildingMarkers.appendChild(marker);
      }
    }

    function renderSelectedPointMarker() {
      selectedPointMarker.style.display = "none";
      if (!currentViewProjection || gameState.selectedPoint === null) return;
      const point = pointVectorForId(gameState.selectedPoint.id);
      if (!point || !frontFacingPoint(point.x, point.y, point.z)) return;
      const projected = projectPoint(currentViewProjection, point.x, point.y, point.z);
      if (!projected) return;
      selectedPointMarker.style.display = "block";
      selectedPointMarker.style.left = `${projected.x}px`;
      selectedPointMarker.style.top = `${projected.y}px`;
    }

    function focusPointById(pointId) {
      const point = pointVectorForId(pointId);
      if (!point) return;
      rotationY = Math.atan2(-point.x, point.z);
      const horizontalZ = Math.sqrt(point.x * point.x + point.z * point.z);
      rotationX = Math.atan2(-point.y, horizontalZ);
      rotationZ = 0.0;
      zoom = Math.max(zoom, 2.4);
      selectPointById(pointId);
      refreshActiveLevel();
      draw();
    }

    function selectNearestPoint(clientX, clientY) {
      if (activeIndex !== levels.length - 1) {
        gameState.selectedPoint = null;
        pushStatus("Выбор точки доступен только на максимальном LOD.");
        return;
      }
      if (!currentViewProjection) draw();
      const rect = canvas.getBoundingClientRect();
      const targetX = clientX - rect.left;
      const targetY = clientY - rect.top;
      const level = levels[activeIndex];
      const stride = Math.max(1, Math.floor(level.count / 7000));
      let bestIndex = -1;
      let bestDistance = Infinity;
      for (let index = 0; index < level.count; index += stride) {
        const offset = index * 3;
        const x = level.positions[offset];
        const y = level.positions[offset + 1];
        const z = level.positions[offset + 2];
        if (!frontFacingPoint(x, y, z)) continue;
        const projected = projectPoint(
          currentViewProjection,
          x,
          y,
          z,
        );
        if (!projected) continue;
        const dx = projected.x - targetX;
        const dy = projected.y - targetY;
        const distance = dx * dx + dy * dy;
        if (distance < bestDistance) {
          bestDistance = distance;
          bestIndex = index;
        }
      }
      if (bestIndex >= 0) {
        if (selectPointById(bestIndex)) {
          pushStatus(`Выбрана точка #${bestIndex}.`);
          draw();
        }
      }
    }

    function refreshActiveLevel() {
      const next = pickLevel(zoom);
      if (next !== activeIndex) {
        activeIndex = next;
      }
      updateStats();
      renderGameUi();
    }

    function applyZoom(factor) {
      zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zoom * factor));
      refreshActiveLevel();
      draw();
    }

    function clampPitch(value) {
      return value;
    }

    function wrapAngle(value) {
      const fullTurn = Math.PI * 2;
      while (value > Math.PI) value -= fullTurn;
      while (value < -Math.PI) value += fullTurn;
      return value;
    }

    function resetCamera() {
      const cityCenter = gameState.buildings.find((building) => building.id === "city_center");
      if (cityCenter && cityCenter.pointId !== null) {
        zoom = 2.4;
        focusPointById(cityCenter.pointId);
      } else {
        rotationX = -0.28;
        rotationY = 0.54;
        rotationZ = 0.0;
        zoom = 1.0;
        refreshActiveLevel();
        draw();
      }
    }

    function isTextEntryTarget(target) {
      if (!target) return false;
      const tag = target.tagName;
      return tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable;
    }

    function processKeys(timestamp) {
      const last = lastKeyTimestamp || timestamp;
      const elapsed = Math.min(64, timestamp - last);
      lastKeyTimestamp = timestamp;
      const stepScale = elapsed / 16;
      const rotationStep = KEY_ROTATE_STEP * stepScale;
      let changed = false;

      if (pressedKeys.has("w")) { rotationX = wrapAngle(clampPitch(rotationX - rotationStep)); changed = true; }
      if (pressedKeys.has("s")) { rotationX = wrapAngle(clampPitch(rotationX + rotationStep)); changed = true; }
      if (pressedKeys.has("a")) { rotationY = wrapAngle(rotationY - rotationStep); changed = true; }
      if (pressedKeys.has("d")) { rotationY = wrapAngle(rotationY + rotationStep); changed = true; }
      if (pressedKeys.has("q")) { rotationZ = wrapAngle(rotationZ - rotationStep); changed = true; }
      if (pressedKeys.has("e")) { rotationZ = wrapAngle(rotationZ + rotationStep); changed = true; }

      if (changed) draw();

      if (pressedKeys.size === 0) {
        keyAnimationHandle = null;
        lastKeyTimestamp = 0;
      } else {
        keyAnimationHandle = window.requestAnimationFrame(processKeys);
      }
    }

    function ensureKeyAnimation() {
      if (keyAnimationHandle === null && pressedKeys.size > 0) {
        lastKeyTimestamp = 0;
        keyAnimationHandle = window.requestAnimationFrame(processKeys);
      }
    }

    canvas.addEventListener("pointerdown", (event) => {
      dragging = true;
      movedDuringDrag = false;
      pointerX = event.clientX;
      pointerY = event.clientY;
      canvas.setPointerCapture(event.pointerId);
      canvas.focus({ preventScroll: true });
    });

    canvas.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      const dx = event.clientX - pointerX;
      const dy = event.clientY - pointerY;
      pointerX = event.clientX;
      pointerY = event.clientY;
      if (Math.abs(dx) + Math.abs(dy) > 3) movedDuringDrag = true;
      rotationY = wrapAngle(rotationY + dx * POINTER_ROTATE_STEP);
      rotationX = wrapAngle(clampPitch(rotationX + dy * POINTER_ROTATE_STEP));
      draw();
    });

    canvas.addEventListener("pointerup", (event) => {
      const wasClick = dragging && !movedDuringDrag;
      dragging = false;
      if (wasClick) selectNearestPoint(event.clientX, event.clientY);
    });

    canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      applyZoom(event.deltaY > 0 ? 0.92 : 1.08);
    }, { passive: false });

    document.getElementById("zoomIn").addEventListener("click", () => {
      applyZoom(KEY_ZOOM_STEP);
      canvas.focus({ preventScroll: true });
    });
    document.getElementById("zoomOut").addEventListener("click", () => {
      applyZoom(1 / KEY_ZOOM_STEP);
      canvas.focus({ preventScroll: true });
    });
    document.getElementById("reset").addEventListener("click", () => {
      resetCamera();
      canvas.focus({ preventScroll: true });
    });
    document.getElementById("loginButton").addEventListener("click", () => {
      const nickname = nicknameInput.value.trim() || "Игрок1";
      gameState.nickname = nickname;
      pushStatus(`Игрок ${nickname} вошёл под выбранным ником.`);
      canvas.focus({ preventScroll: true });
    });
    pauseButton.addEventListener("click", () => {
      gameState.paused = !gameState.paused;
      pushStatus(gameState.paused ? "Время остановлено." : "Время запущено.");
      canvas.focus({ preventScroll: true });
    });
    document.getElementById("stepWeekButton").addEventListener("click", () => {
      advanceWeek();
      canvas.focus({ preventScroll: true });
    });
    document.getElementById("skipMonthButton").addEventListener("click", () => {
      advancePeriod(WEEKS_PER_MONTH, "Месяц");
      canvas.focus({ preventScroll: true });
    });
    document.getElementById("skipYearButton").addEventListener("click", () => {
      advancePeriod(WEEKS_PER_MONTH * MONTHS_PER_YEAR, "Год");
      canvas.focus({ preventScroll: true });
    });
    document.getElementById("gridLayerButton").addEventListener("click", () => {
      gameState.layers.grid = !gameState.layers.grid;
      draw();
      pushStatus(gameState.layers.grid ? "Слой меридианов и параллелей включён." : "Слой меридианов и параллелей скрыт.");
      canvas.focus({ preventScroll: true });
    });
    selectedPointPanel.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-building-action]");
      if (!button) return;
      if (button.dataset.buildingAction === "toggle") toggleSelectedBuilding();
      if (button.dataset.buildingAction === "demolish") demolishSelectedBuilding();
      canvas.focus({ preventScroll: true });
    });

    window.setInterval(() => {
      if (!gameState.paused) advanceWeek();
    }, WEEK_SECONDS * 1000);

    window.addEventListener("keydown", (event) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isTextEntryTarget(event.target)) return;
      const key = event.key.toLowerCase();
      if (["w", "a", "s", "d", "q", "e"].includes(key)) {
        if (!pressedKeys.has(key)) { pressedKeys.add(key); ensureKeyAnimation(); }
        event.preventDefault();
        return;
      }
      if (key === "r") { resetCamera(); event.preventDefault(); return; }
      if (key === "+" || key === "=") { applyZoom(KEY_ZOOM_STEP); event.preventDefault(); return; }
      if (key === "-" || key === "_") { applyZoom(1 / KEY_ZOOM_STEP); event.preventDefault(); return; }
    });

    window.addEventListener("keyup", (event) => {
      const key = event.key.toLowerCase();
      if (pressedKeys.delete(key)) event.preventDefault();
    });

    window.addEventListener("blur", () => { pressedKeys.clear(); });
    window.addEventListener("resize", draw);

    canvas.style.width = "100vw";
    canvas.style.height = "100vh";
    gridOverlay.style.width = "100vw";
    gridOverlay.style.height = "100vh";
    canvas.focus({ preventScroll: true });
    renderBiomeLegend();
    refreshActiveLevel();
    renderGameUi();
    resetCamera();
  </script>
</body>
</html>
"""

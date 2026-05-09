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
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px;
    }

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
  </style>
</head>
<body>
  <canvas id="planet" tabindex="0"></canvas>
  <div class="hud" aria-live="polite">
    <div class="panel" id="stats"></div>
    <div class="panel" id="lod"></div>
    <div class="panel help">
      <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> rotate &middot;
      <kbd>Q</kbd><kbd>E</kbd> roll &middot;
      <kbd>+</kbd><kbd>-</kbd> zoom &middot;
      <kbd>R</kbd> reset
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
  </div>
  <div class="tools">
    <button id="zoomIn" title="Zoom in" aria-label="Zoom in">+</button>
    <button id="zoomOut" title="Zoom out" aria-label="Zoom out">-</button>
    <button id="reset" title="Reset camera" aria-label="Reset camera">R</button>
  </div>
  <aside class="sidebar">
    <div class="panel" id="resourcesPanel"></div>
    <div class="panel" id="demographicsPanel"></div>
    <div class="panel" id="selectedPointPanel"></div>
    <div class="panel">
      <h2>Постройки</h2>
      <div class="buildingList" id="buildingMenu"></div>
    </div>
    <div class="panel">
      <h2>Политика</h2>
      <div id="policyPanel"></div>
    </div>
    <div class="panel">
      <h2>Статус</h2>
      <div class="statusLog" id="statusLog"></div>
    </div>
  </aside>
  <div class="error" id="error"></div>

  <script>
    const payload = __SPHERE_PAYLOAD__;
    const canvas = document.getElementById("planet");
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
    const policyPanel = document.getElementById("policyPanel");
    const statusLog = document.getElementById("statusLog");

    const ZOOM_MIN = 0.55;
    const ZOOM_MAX = 8.0;
    const KEY_ROTATE_STEP = 0.05;
    const KEY_ZOOM_STEP = 1.10;
    const WEEK_SECONDS = 5; // tick every 5 seconds
    const FEATURE_RIVER = 1;
    const FEATURE_LAKE = 2;
    const FEATURE_MOUNTAIN = 4;
    const FEATURE_ISLAND = 8;
    const POLICY_COLORS = {
      own: "#2fb344",
      neutral: "#2f80ed",
      enemy: "#d63031",
      ally: "#f2c94c",
    };
    const BUILDINGS = [
      { id: "warehouse", label: "Склад", cost: { stone: 3, roundwood: 2 }, requires: [], vacancies: 0 },
      { id: "quarry", label: "Карьер", cost: { stone: 4 }, requires: ["warehouse"], vacancies: 3 },
      { id: "stone_quarry", label: "Каменоломня", cost: { stone: 8, roundwood: 2 }, requires: ["warehouse"], vacancies: 4 },
      { id: "lumberjack_site", label: "Место дровосека", cost: { stone: 2, tools: 0.2 }, requires: ["stone_quarry"], vacancies: 4 },
      { id: "housing1", label: "Жильё1", cost: { clay: 5 }, requires: ["warehouse"], vacancies: 0, capacity: 5 },
      { id: "housing2", label: "Жильё2", cost: { roundwood: 12 }, requires: ["lumberjack_site"], vacancies: 0, capacity: 25 },
      { id: "housing3", label: "Жильё3", cost: { plank: 28 }, requires: ["sawmill"], vacancies: 0, capacity: 100 },
      { id: "housing4", label: "Жильё4", cost: { brick: 120 }, requires: ["brick_factory"], vacancies: 0, capacity: 500 },
      { id: "housing5", label: "Жильё5", cost: { concrete: 1100, metal: 120 }, requires: ["foundry"], vacancies: 0, capacity: 5000 },
      { id: "brick_factory", label: "Кирпичный завод", cost: { stone: 12, roundwood: 4 }, requires: ["stone_quarry"], vacancies: 6 },
      { id: "forge", label: "Кузня", cost: { stone: 18, roundwood: 6 }, requires: ["stone_quarry"], vacancies: 4 },
      { id: "sawmill", label: "Лесопилка", cost: { stone: 8, roundwood: 8 }, requires: ["lumberjack_site"], vacancies: 4 },
      { id: "foundry", label: "Литейный завод", cost: { stone: 20, brick: 10 }, requires: ["forge"], vacancies: 8 },
    ];
    const gameState = {
      nickname: "Игрок1",
      paused: true,
      week: 0,
      day: 0,
      selectedPoint: null,
      resources: {
        food: 6480,
        water: 10800,
        roundwood: 80,
        wood: 40,
        stone: 80,
        sand: 30,
        clay: 40,
        raw_metal: 12,
        tools: 2,
        heat: 120,
      },
      people: { adults: 10, children: 0 },
      buildings: [
        { id: "warehouse", pointId: null, relation: "own" },
        { id: "housing2", pointId: null, relation: "own" },
      ],
      status: ["Игрок Игрок1 вошёл в игру: 10 жителей, запас еды и воды на год."],
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
      uniform float uPointScale;
      uniform float uPlanetRadius;
      out vec3 vColor;
      out vec3 vNormal;

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
        vColor = biomeColor(aBiome);
        if (hasFeature(aFeature, 1.0)) vColor = mix(vColor, vec3(0.170, 0.720, 0.930), 0.72);
        if (hasFeature(aFeature, 2.0)) vColor = vec3(0.180, 0.560, 0.720);
        if (hasFeature(aFeature, 4.0)) vColor = mix(vColor, vec3(0.760, 0.760, 0.720), 0.48);
        vNormal = aPosition;
      }
    `;

    const FRAGMENT_SHADER = `#version 300 es
      precision highp float;
      in vec3 vColor;
      in vec3 vNormal;
      out vec4 fragColor;
      uniform vec3 uLight;

      void main() {
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

    function resourceLabel(name) {
      return {
        food: "еда",
        water: "вода",
        roundwood: "брёвна",
        wood: "древесина",
        stone: "камень",
        sand: "песок",
        clay: "глина",
        raw_metal: "сырая руда",
        tools: "инструменты",
        heat: "тепло",
        plank: "доски",
        brick: "кирпич",
        metal: "металл",
        concrete: "бетон",
      }[name] || name;
    }

    function formatCost(cost) {
      const parts = Object.entries(cost || {}).map(([name, amount]) =>
        `${resourceLabel(name)} ${amount}`,
      );
      return parts.length ? parts.join(", ") : "без затрат";
    }

    function hasBuilding(id) {
      return gameState.buildings.some((building) => building.id === id);
    }

    function canAfford(cost) {
      return Object.entries(cost || {}).every(([name, amount]) =>
        (gameState.resources[name] || 0) >= amount,
      );
    }

    function availableBuildings() {
      return BUILDINGS.filter((building) =>
        building.requires.every((required) => hasBuilding(required)),
      );
    }

    function currentDemographics() {
      const vacancies = gameState.buildings.reduce((total, building) => {
        const definition = BUILDINGS.find((item) => item.id === building.id);
        return total + (definition ? definition.vacancies || 0 : 0);
      }, 0);
      const adults = gameState.people.adults;
      const children = gameState.people.children;
      return {
        adults,
        children,
        vacancies,
        unemployed: Math.max(0, adults - vacancies),
      };
    }

    function pushStatus(message) {
      gameState.status.unshift(message);
      gameState.status = gameState.status.slice(0, 8);
      renderGameUi();
    }

    function renderGameUi() {
      const demographics = currentDemographics();
      timePanel.textContent = gameState.paused
        ? `Пауза | неделя ${gameState.week} | планирование доступно`
        : `Время идёт | неделя ${gameState.week} | тик 1 неделя / ${WEEK_SECONDS} c`;
      pauseButton.textContent = gameState.paused ? "▶" : "Ⅱ";

      const resourceEntries = Object.entries(gameState.resources)
        .filter(([, amount]) => amount > 0.001)
        .slice(0, 12)
        .map(([name, amount]) => `<span>${resourceLabel(name)} ${amount.toFixed(1)} т</span>`)
        .join("");
      resourcesPanel.innerHTML = `<h2>Склад</h2><div class="resourceGrid">${resourceEntries}</div>`;
      demographicsPanel.innerHTML =
        `<h2>Демография</h2>` +
        `<p>взрослые ${demographics.adults} · дети ${demographics.children} · ` +
        `безработные ${demographics.unemployed} · вакансии ${demographics.vacancies}</p>`;

      if (gameState.selectedPoint === null) {
        selectedPointPanel.innerHTML =
          `<h2>Точка</h2><p>Выбор активен только на максимальном LOD.</p>`;
      } else {
        const point = gameState.selectedPoint;
        const flags = point.features;
        const featureNames = [];
        if (flags & FEATURE_RIVER) featureNames.push("река");
        if (flags & FEATURE_LAKE) featureNames.push("озеро");
        if (flags & FEATURE_MOUNTAIN) featureNames.push("горы");
        if (flags & FEATURE_ISLAND) featureNames.push("редкий остров");
        selectedPointPanel.innerHTML =
          `<h2>Точка #${point.id}</h2>` +
          `<p>LOD ${activeIndex + 1}, высота ${point.elevation} м` +
          `${featureNames.length ? `, ${featureNames.join(", ")}` : ""}</p>`;
      }

      buildingMenu.innerHTML = "";
      for (const building of availableBuildings()) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = `${building.label} · ${formatCost(building.cost)}`;
        const disabled = gameState.selectedPoint === null || !canAfford(building.cost);
        button.disabled = disabled;
        button.addEventListener("click", () => planBuilding(building));
        buildingMenu.appendChild(button);
      }

      policyPanel.innerHTML = Object.entries(POLICY_COLORS)
        .map(([name, color]) => `<span style="color:${color}">■</span> ${name}`)
        .join(" · ");
      statusLog.innerHTML = gameState.status.map((item) => `<div>${item}</div>`).join("");
    }

    function planBuilding(building) {
      if (gameState.selectedPoint === null || !canAfford(building.cost)) return;
      for (const [name, amount] of Object.entries(building.cost || {})) {
        gameState.resources[name] = Math.max(0, (gameState.resources[name] || 0) - amount);
      }
      gameState.buildings.push({
        id: building.id,
        pointId: gameState.selectedPoint.id,
        relation: "own",
      });
      pushStatus(`${gameState.nickname}: ${building.label} запланирована в точке #${gameState.selectedPoint.id}.`);
    }

    function advanceWeek() {
      gameState.week += 1;
      gameState.day += 7;
      const people = gameState.people.adults + gameState.people.children;
      gameState.resources.food = (gameState.resources.food || 0) - people * 1.8 * 7;
      gameState.resources.water = (gameState.resources.water || 0) - people * 3.0 * 7;

      for (const building of gameState.buildings) {
        if (building.id === "quarry") {
          gameState.resources.stone = (gameState.resources.stone || 0) + 14;
          gameState.resources.sand = (gameState.resources.sand || 0) + 7;
          gameState.resources.clay = (gameState.resources.clay || 0) + 7;
        }
        if (building.id === "stone_quarry") {
          gameState.resources.stone = (gameState.resources.stone || 0) + 28;
          gameState.resources.raw_metal = (gameState.resources.raw_metal || 0) + 4.2;
        }
        if (building.id === "lumberjack_site") {
          gameState.resources.roundwood = (gameState.resources.roundwood || 0) + 28;
        }
      }

      if (gameState.resources.water < 0 || gameState.resources.food < 0) {
        const cause = gameState.resources.water < 0 ? "жажды" : "голода";
        gameState.resources.water = Math.max(0, gameState.resources.water);
        gameState.resources.food = Math.max(0, gameState.resources.food);
        if (gameState.people.adults > 0) {
          gameState.people.adults -= 1;
          pushStatus(`Чел${gameState.people.adults + 1} умер от ${cause}.`);
          return;
        }
      }
      pushStatus(`Неделя ${gameState.week}: склад обновлён, время можно поставить на паузу.`);
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
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

      const aspect = canvas.width / Math.max(1, canvas.height);
      const projection = buildPerspective(aspect);
      const view = viewMatrix();
      const viewProjection = multiply(projection, view);
      currentViewProjection = viewProjection;
      gl.uniformMatrix4fv(uViewProjection, false, viewProjection);

      const level = levels[activeIndex];
      const densityFactor = Math.sqrt(20000 / Math.max(1, level.count));
      const baseScale = Math.min(canvas.width, canvas.height) * 0.012 * densityFactor;
      const pointScale = baseScale * Math.pow(zoom, 0.6);
      gl.uniform1f(uPointScale, pointScale);

      gl.bindVertexArray(level.vao);
      gl.drawArrays(gl.POINTS, 0, level.count);
      gl.bindVertexArray(null);
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
        const projected = projectPoint(
          currentViewProjection,
          level.positions[offset],
          level.positions[offset + 1],
          level.positions[offset + 2],
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
        gameState.selectedPoint = {
          id: bestIndex,
          elevation: level.elevations[bestIndex],
          features: level.features[bestIndex],
        };
        pushStatus(`Выбрана точка #${bestIndex}.`);
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
      return Math.max(-1.35, Math.min(1.35, value));
    }

    function resetCamera() {
      rotationX = -0.28;
      rotationY = 0.54;
      rotationZ = 0.0;
      zoom = 1.0;
      refreshActiveLevel();
      draw();
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

      if (pressedKeys.has("w")) { rotationX = clampPitch(rotationX - rotationStep); changed = true; }
      if (pressedKeys.has("s")) { rotationX = clampPitch(rotationX + rotationStep); changed = true; }
      if (pressedKeys.has("a")) { rotationY -= rotationStep; changed = true; }
      if (pressedKeys.has("d")) { rotationY += rotationStep; changed = true; }
      if (pressedKeys.has("q")) { rotationZ -= rotationStep; changed = true; }
      if (pressedKeys.has("e")) { rotationZ += rotationStep; changed = true; }

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
      rotationY += dx * 0.008;
      rotationX = clampPitch(rotationX + dy * 0.008);
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
    canvas.focus({ preventScroll: true });
    refreshActiveLevel();
    renderGameUi();
    draw();
  </script>
</body>
</html>
"""

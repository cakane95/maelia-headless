import { useState, useEffect, useRef } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import "./App.css";

const API_URL = "http://localhost:8000";

const STATES = {
  IDLE: "idle",
  LOADING: "loading",
  LOADED: "loaded",
  RUNNING: "running",
  PAUSED: "paused",
  FINISHED: "finished",
};

const DEFAULT_PARAMS = {
  anneeDebutSimulation: 2018,
  nbAnneesSimulation: 2,
  nomDecoupageZonePourLectureFichiers: "sasseme",
  executerEcritureFichiers: true,
  sorties_eau: true,
  sorties_azote: true,
  sorties_carboneGES: true,
};

const META_KEYS = [
  "simulation_ended",
  "simulation_status_message",
  "simulation_output_available",
];

function toIncludesName(name) {
  return name.startsWith("includes_") ? name : `includes_${name}`;
}

function buildGamaParameters(params) {
  return [
    { type: "int", name: "anneeDebutSimulation", value: params.anneeDebutSimulation },
    { type: "int", name: "nbAnneesSimulation", value: params.nbAnneesSimulation },
    { type: "string", name: "nomDecoupageZonePourLectureFichiers", value: toIncludesName(params.nomDecoupageZonePourLectureFichiers) },
    { type: "bool", name: "executerEcritureFichiers", value: params.executerEcritureFichiers },
    { type: "bool", name: "sorties_eau", value: params.sorties_eau },
    { type: "bool", name: "sorties_azote", value: params.sorties_azote },
    { type: "bool", name: "sorties_carboneGES", value: params.sorties_carboneGES },
  ];
}

async function call(path, method = "POST", body = null) {
  const options = { method };
  if (body) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }
  const res = await fetch(`${API_URL}/simulation${path}`, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

async function uploadIncludesZip(territory, zipFile) {
  const formData = new FormData();

  formData.append("territory", territory);
  formData.append("file", zipFile);

  const res = await fetch(`${API_URL}/simulation/includes/upload`, {
    method: "POST",
    body: formData,
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`);
  }

  return data;
}

function Toggle({ checked, onChange }) {
  return (
    <button
      className={`toggle ${checked ? "toggle-on" : "toggle-off"}`}
      onClick={() => onChange(!checked)}
      type="button"
    >
      <span className="toggle-thumb" />
    </button>
  );
}

export default function App() {
  const [state, setState] = useState(STATES.IDLE);
  const [expId, setExpId] = useState(null);
  const [error, setError] = useState(null);
  const [charts, setCharts] = useState({});
  const [endMessage, setEndMessage] = useState(null);
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [zipFile, setZipFile] = useState(null);
  const pollRef = useRef(null);
  const [outputsAvailable, setOutputsAvailable] = useState(false);

  const setParam = (key, value) => setParams((p) => ({ ...p, [key]: value }));

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const data = await call("/realtime", "GET");
        setCharts(data);
        setOutputsAvailable(Boolean(data.simulation_output_available));
        if (data.simulation_ended) {
          stopPolling();
          setEndMessage(data.simulation_status_message || "Simulation terminée");
          setState(STATES.FINISHED);
          setExpId(null);
        }
      } catch (_) {}
    }, 1500);
  };

  useEffect(() => () => stopPolling(), []);

  const handle = async (action) => {
    setError(null);
    try {
      if (action === "start") {
      setEndMessage(null);
      setOutputsAvailable(false);
      setCharts({});
      setState(STATES.LOADING);

      await uploadIncludesZip(
        params.nomDecoupageZonePourLectureFichiers,
        zipFile
      );

      const gamaParams = buildGamaParameters(params);
      const data = await call("/load", "POST", { parameters: gamaParams });

      setExpId(data.experiment_id);
      setState(STATES.LOADED);
    } else if (action === "play") {
        await call("/play");
        setState(STATES.RUNNING);
        startPolling();
      } else if (action === "pause") {
        await call("/pause");
        setState(STATES.PAUSED);
        stopPolling();
      } else if (action === "step") {
        await call("/step");
        const data = await call("/realtime", "GET");
        setCharts(data);
        setOutputsAvailable(Boolean(data.simulation_output_available));
        setState(STATES.PAUSED);
      } else if (action === "stop") {
        await call("/stop");
        stopPolling();
        setExpId(null);
        setCharts({});
        setEndMessage(null);
        setOutputsAvailable(false);
        setZipFile(null);
        setState(STATES.IDLE);
      }
    } catch (e) {
      setError(e.message);
      if (action === "start") setState(STATES.IDLE);
    }
  };

  const hasCharts = Object.keys(charts).filter(
  (k) => !META_KEYS.includes(k)
).length > 0;

  function getChartValues(chart) {
    if (!chart?.data || !chart?.series) return [];
    return chart.data
      .flatMap((point) => chart.series.map((s) => Number(point[s.key])))
      .filter((value) => Number.isFinite(value));
  }

  function getYAxisDomain(chart) {
    const values = getChartValues(chart);
    if (values.length === 0) return [0, 1];
    const min = Math.min(...values);
    const max = Math.max(...values);
    if (min === max) {
      if (min === 0) return [0, 1];
      const padding = Math.abs(min) * 0.1;
      return [min - padding, max + padding];
    }
    const padding = (max - min) * 0.1;
    return [min >= 0 ? 0 : min - padding, max + padding];
  }

  const downloadOutputs = () => {
    window.location.href = `${API_URL}/simulation/outputs/download`;
  };

  return (
    <main className="page">
      <section className="card">
        <div className="card-header">
          <div>
            <p className="eyebrow">MAELIA + GAMA Headless</p>
            <h1>Simulation</h1>
          </div>
          {expId && <span className="exp-id">exp {expId}</span>}
        </div>

        {state === STATES.IDLE && (
          <>
            <div className="params">

              {/* Section 1 — Territoire + Upload */}
              <div className="param-row">
                <label className="param-label">Territoire</label>
                <div className="param-input-group">
                  <span className="param-prefix">includes_</span>
                  <input
                    type="text"
                    value={params.nomDecoupageZonePourLectureFichiers}
                    onChange={(e) => setParam("nomDecoupageZonePourLectureFichiers", e.target.value)}
                    className="param-input"
                  />
                </div>
              </div>

              <div className="param-row">
                <label className="param-label">Dossier includes</label>
                <label className={`upload-zone ${zipFile ? "upload-zone-ok" : ""}`}>
                  <input
                    type="file"
                    accept=".zip"
                    style={{ display: "none" }}
                    onChange={(e) => setZipFile(e.target.files[0] || null)}
                  />
                  {zipFile ? `✓ ${zipFile.name}` : "Déposer un .zip"}
                </label>
              </div>

              <div className="param-divider" />

              {/* Section 2 — Sliders */}
              <div className="param-row">
                <label className="param-label">Année de début</label>
                <div className="param-slider-group">
                  <input
                    type="range"
                    min={1990}
                    max={2030}
                    step={1}
                    value={params.anneeDebutSimulation}
                    onChange={(e) => setParam("anneeDebutSimulation", Number(e.target.value))}
                    className="param-slider"
                  />
                  <span className="param-value">{params.anneeDebutSimulation}</span>
                </div>
              </div>

              <div className="param-row">
                <label className="param-label">Nombre d'années</label>
                <div className="param-slider-group">
                  <input
                    type="range"
                    min={1}
                    max={10}
                    step={1}
                    value={params.nbAnneesSimulation}
                    onChange={(e) => setParam("nbAnneesSimulation", Number(e.target.value))}
                    className="param-slider"
                  />
                  <span className="param-value">{params.nbAnneesSimulation}</span>
                </div>
              </div>

              <div className="param-divider" />

              {/* Section 3 — Toggles */}
              {[
                { key: "executerEcritureFichiers", label: "Écriture des fichiers" },
                { key: "sorties_eau", label: "Sorties eau" },
                { key: "sorties_azote", label: "Sorties azote" },
                { key: "sorties_carboneGES", label: "Sorties carbone et GES" },
              ].map(({ key, label }) => (
                <div className="param-row" key={key}>
                  <label className="param-label">{label}</label>
                  <Toggle
                    checked={params[key]}
                    onChange={(v) => setParam(key, v)}
                  />
                </div>
              ))}
            </div>

            <button
              className="btn btn-primary btn-full"
              onClick={() => handle("start")}
              disabled={!zipFile}
            >
              Commencer une simulation
            </button>
          </>
        )}

        {state === STATES.LOADING && (
          <button className="btn btn-primary btn-full" disabled>
            Chargement du modèle...
          </button>
        )}

        {[STATES.LOADED, STATES.RUNNING, STATES.PAUSED].includes(state) && (
          <div className="player">
            {state === STATES.LOADED && (
              <button className="btn btn-primary" onClick={() => handle("play")}>
                ▶ Play
              </button>
            )}
            {state === STATES.RUNNING && (
              <button className="btn btn-primary" onClick={() => handle("pause")}>
                ⏸ Pause
              </button>
            )}
            {state === STATES.PAUSED && (
              <>
                <button className="btn btn-primary" onClick={() => handle("play")}>
                  ▶ Play
                </button>
                <button className="btn btn-secondary" onClick={() => handle("step")}>
                  Step
                </button>
              </>
            )}
            <button className="btn btn-close" onClick={() => handle("stop")} title="Fermer">
              ✕
            </button>
          </div>
        )}

        {state === STATES.FINISHED && (
          <div className="end-message">
            <p>{endMessage}</p>
            <div className="end-actions">
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setEndMessage(null);
                  setCharts({});
                  setExpId(null);
                  setZipFile(null);
                  setOutputsAvailable(false);
                  setState(STATES.IDLE);
                }}
              >
                Nouvelle simulation
              </button>
              <button
                className="btn btn-secondary"
                disabled={!outputsAvailable}
                onClick={downloadOutputs}
              >
                Télécharger les sorties
              </button>
            </div>
          </div>
        )}

        {error && <p className="error">{error}</p>}
      </section>

      {hasCharts && (
        <div className="charts-grid">
          {Object.entries(charts)
            .filter(([k]) => !META_KEYS.includes(k))
            .map(([key, chart]) => (
              <section className="chart-card" key={key}>
                <p className="chart-title">{chart.title}</p>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chart.data}>
                    <XAxis
                      dataKey={chart.xKey}
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      type="number"
                      domain={getYAxisDomain(chart)}
                      allowDataOverflow={false}
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                      width={50}
                    />
                    <Tooltip
                      contentStyle={{
                        fontSize: 12,
                        border: "0.5px solid #e2e8f0",
                        borderRadius: 8,
                        boxShadow: "none",
                      }}
                    />
                    {chart.series.map((s) => (
                      <Line
                        key={s.key}
                        type="monotone"
                        dataKey={s.key}
                        name={`${s.label} (${s.unit})`}
                        stroke={s.color || "#2563eb"}
                        strokeWidth={1.5}
                        dot={chart.data.length <= 100 ? { r: 2 } : false}
                        isAnimationActive={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </section>
            ))}
        </div>
      )}
    </main>
  );
}
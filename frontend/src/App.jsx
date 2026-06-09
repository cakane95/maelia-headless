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

async function call(path, method = "POST") {
  const res = await fetch(`${API_URL}/simulation${path}`, { method });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

export default function App() {
  const [state, setState] = useState(STATES.IDLE);
  const [expId, setExpId] = useState(null);
  const [error, setError] = useState(null);
  const [charts, setCharts] = useState({});
  const [endMessage, setEndMessage] = useState(null);
  const pollRef = useRef(null);

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
        setState(STATES.LOADING);
        const data = await call("/load");
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
        setState(STATES.PAUSED);
      } else if (action === "stop") {
        await call("/stop");
        stopPolling();
        setExpId(null);
        setCharts({});
        setEndMessage(null);
        setState(STATES.IDLE);
      }
    } catch (e) {
      setError(e.message);
      if (action === "start") setState(STATES.IDLE);
    }
  };

  const hasCharts = Object.keys(charts).filter(k =>
    !["simulation_ended", "simulation_status_message"].includes(k)
  ).length > 0;

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
          <button
            className="btn btn-primary btn-full"
            onClick={() => handle("start")}
          >
            Commencer une simulation
          </button>
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
            <button
              className="btn btn-close"
              onClick={() => handle("stop")}
              title="Fermer"
            >
              ✕
            </button>
          </div>
        )}

        {state === STATES.FINISHED && (
          <div className="end-message">
            <p>{endMessage}</p>
            <button
              className="btn btn-secondary"
              onClick={() => {
                setEndMessage(null);
                setCharts({});
                setState(STATES.IDLE);
              }}
            >
              Nouvelle simulation
            </button>
          </div>
        )}

        {error && <p className="error">{error}</p>}
      </section>

      {hasCharts && (
        <div className="charts-grid">
          {Object.entries(charts)
            .filter(([k]) => !["simulation_ended", "simulation_status_message"].includes(k))
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
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                      width={40}
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
                      dot={false}
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
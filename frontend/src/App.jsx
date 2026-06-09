import { useState } from "react";
import "./App.css";

const API_URL = "http://localhost:8000";

function App() {
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");

  const launchSimulation = async () => {
    setStatus("loading");
    setMessage("Lancement de la simulation MAELIA...");

    try {
      const response = await fetch(`${API_URL}/launch`, {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Erreur HTTP ${response.status}`);
      }

      setStatus("success");
      setMessage(
        `Simulation lancée avec succès. Expérience GAMA : ${data.experiment_id ?? "non renseignée"}`
      );
    } catch (error) {
      setStatus("error");
      setMessage(`Erreur : ${error.message}`);
    }
  };

  return (
    <main className="page">
      <section className="card">
        <p className="eyebrow">MAELIA + GAMA Headless</p>

        <h1>Lancement de simulation MAELIA</h1>

        <p className="description">
          Cette interface déclenche une simulation MAELIA via le backend FastAPI
          et le serveur GAMA headless.
        </p>

        <button
          className="launch-button"
          onClick={launchSimulation}
          disabled={status === "loading"}
        >
          {status === "loading" ? "Lancement en cours..." : "Je lance"}
        </button>

        {message && (
          <div className={`status ${status}`}>
            {message}
          </div>
        )}
      </section>
    </main>
  );
}

export default App;
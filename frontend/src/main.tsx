import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./ui/tokens.css";

// No <StrictMode>: its double-invoked effects would open the editor twice and
// log a duplicate start snapshot into the research data.
createRoot(document.getElementById("app")!).render(<App />);

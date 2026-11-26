import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@/components/arc/foundation.css";
import "./styles.css";
import { App } from "./app";
import { installScrollReveal } from "@/lib/scroll-reveal";
import { initTheme } from "@/lib/theme";

initTheme();
installScrollReveal();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);

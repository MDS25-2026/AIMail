import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "../styles.css";
import ExtensionApp from "./ExtensionApp";
import ExtensionProviders from "./ExtensionProviders";

const root = document.getElementById("root");
if (root === null) throw new Error("sidepanel.html has no #root element");

createRoot(root).render(
  <StrictMode>
    <ExtensionProviders>
      <ExtensionApp />
    </ExtensionProviders>
  </StrictMode>,
);

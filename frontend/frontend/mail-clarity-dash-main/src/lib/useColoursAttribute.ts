import { useEffect } from "react";

import { coloursAttribute, type StatusColours } from "./preferences";

/** Applies the colour set at once; the dashboard's server renders the same attribute on load. */
export function useColoursAttribute(colours: StatusColours): void {
  useEffect(() => {
    const value = coloursAttribute(colours);
    if (value === undefined) document.documentElement.removeAttribute("data-colours");
    else document.documentElement.setAttribute("data-colours", value);
  }, [colours]);
}

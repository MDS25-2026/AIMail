import { createContext, useContext } from "react";

import { NO_DETAILS, type DetailValues } from "./details";

/** The open email's detail values; anything outside an open email shows placeholders as stored. */
export const DetailsContext = createContext<DetailValues>(NO_DETAILS);

export function useDetailValues(): DetailValues {
  return useContext(DetailsContext);
}

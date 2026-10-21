import type { ReactNode } from "react";

import { useIsDemo } from "../demo/mode";
import NotFoundPage from "./NotFoundPage";

/** A page the demo does not have: the visitor meets the normal "not found", never an error. */
export default function NotInDemo({ children }: { children: ReactNode }) {
  const isDemo = useIsDemo();
  if (isDemo) return <NotFoundPage />;
  return children;
}

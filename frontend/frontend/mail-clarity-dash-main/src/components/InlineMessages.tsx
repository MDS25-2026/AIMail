import { cva, type VariantProps } from "class-variance-authority";
import type { ReactNode } from "react";

import { cn } from "../lib/utils";

const alert = cva("text-danger", {
  variants: { size: { sm: "text-sm", xs: "text-xs" } },
  defaultVariants: { size: "sm" },
});

const status = cva("", {
  variants: {
    tone: { success: "text-success", muted: "text-fg-muted" },
    size: { sm: "text-sm", xs: "text-xs" },
  },
  defaultVariants: { tone: "success", size: "sm" },
});

type MessageProps = { children: ReactNode; className?: string };

/** A failure the reader should hear at once: screen readers announce role=alert immediately. */
export function InlineAlert({
  children,
  className,
  size,
}: MessageProps & VariantProps<typeof alert>) {
  return (
    <p role="alert" className={cn(alert({ size }), className)}>
      {children}
    </p>
  );
}

/** A result announced politely, after whatever the reader is doing. */
export function InlineStatus({
  children,
  className,
  tone,
  size,
}: MessageProps & VariantProps<typeof status>) {
  return (
    <p role="status" className={cn(status({ tone, size }), className)}>
      {children}
    </p>
  );
}

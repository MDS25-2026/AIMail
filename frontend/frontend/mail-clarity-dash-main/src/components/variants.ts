import { cva, type VariantProps } from "class-variance-authority";

/** The dashboard's buttons, so a new screen picks a role instead of copying a class string. */
export const button = cva(
  // min-h-11: a 44px touch target on a phone (WCAG 2.5.5); desktop keeps its compact sizes.
  "inline-flex min-h-11 items-center justify-center rounded-md font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed md:min-h-0",
  {
    variants: {
      intent: {
        primary:
          "bg-brand font-semibold text-on-brand hover:bg-brand-strong disabled:bg-surface-sunken disabled:text-fg-subtle",
        secondary:
          "border border-line-strong bg-surface text-fg-body hover:bg-surface-muted disabled:text-fg-subtle",
        quiet: "border border-line text-fg-body hover:bg-surface-muted disabled:opacity-60",
        danger:
          "border border-danger-line font-semibold text-danger hover:bg-danger-soft focus-visible:outline-danger disabled:opacity-60",
        dangerSolid:
          "bg-danger font-semibold text-on-brand hover:opacity-90 focus-visible:outline-danger disabled:opacity-50",
        warningSolid: "border border-warning bg-warning font-semibold text-surface",
      },
      size: {
        xs: "px-2 py-1 text-xs",
        sm: "px-3 py-1.5 text-sm",
        // px-3 on a phone: Regenerate, Send later and Approve & Send fit one row at 375px.
        md: "px-3 py-2 text-sm md:px-4",
      },
    },
    defaultVariants: { intent: "secondary", size: "sm" },
  },
);

export type ButtonVariants = VariantProps<typeof button>;

/** One option of a two-way switch (tone, draft or changes); the pressed one is raised. */
export const segment = cva(
  "min-h-11 rounded px-2.5 py-1 text-xs font-medium transition-colors md:min-h-0",
  {
    variants: {
      isPressed: {
        true: "bg-surface text-fg shadow-sm",
        false: "text-fg-muted hover:text-fg-body",
      },
    },
  },
);

/** Text inputs, text areas and selects. */
export const field = cva(
  "min-h-11 md:min-h-0 rounded-md border border-line-strong bg-surface text-fg placeholder:text-fg-subtle focus-visible:outline-2 focus-visible:outline-brand disabled:bg-surface-muted disabled:text-fg-subtle",
  {
    variants: {
      size: {
        sm: "px-2 py-1 text-sm",
        md: "px-3 py-2 text-sm",
      },
    },
    defaultVariants: { size: "md" },
  },
);

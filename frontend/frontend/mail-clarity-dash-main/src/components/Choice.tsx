import { cn } from "../lib/utils";
import { segment } from "./variants";

/** A labelled row of mutually exclusive options, as segmented buttons. */
type ChoiceProps<T extends string> = {
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string; lang?: string }[];
};

/** A segmented radio group: every option visible at once, keyboard-operable as native radios. */
export default function Choice<T extends string>({
  label,
  value,
  onChange,
  options,
}: ChoiceProps<T>) {
  return (
    <fieldset className="flex flex-wrap items-center justify-between gap-2">
      <legend className="float-left text-sm text-fg-muted">{label}</legend>
      <div className="inline-flex flex-wrap rounded-md border border-line bg-surface-muted p-0.5">
        {options.map((option) => (
          <label
            key={option.value}
            lang={option.lang}
            className={cn(
              segment({ isPressed: option.value === value }),
              "inline-flex cursor-pointer items-center focus-within:ring-2 focus-within:ring-brand",
            )}
          >
            <input
              type="radio"
              className="sr-only"
              name={label}
              value={option.value}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

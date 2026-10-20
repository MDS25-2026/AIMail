import { useTranslation } from "react-i18next";

type RemindCheckboxProps = {
  isChecked: boolean;
  disabled: boolean;
  onChange: (isOn: boolean) => void;
};

/** Put the email on the to-do's waiting list whatever it says; unticked, the rules decide. */
export default function RemindCheckbox({ isChecked, disabled, onChange }: RemindCheckboxProps) {
  const { t } = useTranslation();
  return (
    <label className="flex min-h-11 items-center justify-end gap-2 text-xs text-fg-muted md:min-h-0">
      <input
        type="checkbox"
        checked={isChecked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="size-4 accent-[var(--brand)]"
      />
      {t("todo.remindMe")}
    </label>
  );
}

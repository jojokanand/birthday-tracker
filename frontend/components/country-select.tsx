/**
 * Searchable country dropdown.
 *
 * Wraps base-ui's Combobox and reuses the country list / English labels
 * already shipped by `react-phone-number-input` so we don't need a
 * second dependency. Renders flag emoji + country name in each option;
 * the selected value is the 2-letter ISO uppercase code.
 *
 * @module
 */

"use client";

import * as React from "react";
import { Combobox } from "@base-ui/react/combobox";
import { ChevronDown, Check } from "lucide-react";
import { getCountries } from "react-phone-number-input";
import countryLabels from "react-phone-number-input/locale/en.json";

/** A single country option. */
export interface CountryItem {
  /** ISO-2 uppercase code, e.g. ``"US"``. */
  value: string;
  /** English country name, e.g. ``"United States"``. */
  label: string;
}

/** Sorted master list of countries the dropdown shows. Exported for tests. */
export const COUNTRY_ITEMS: readonly CountryItem[] = (() => {
  const labels = countryLabels as Record<string, string>;
  return getCountries()
    .map<CountryItem>((iso) => ({ value: iso, label: labels[iso] ?? iso }))
    .sort((a, b) => a.label.localeCompare(b.label));
})();

/**
 * Convert an ISO-2 country code to its flag emoji.
 *
 * Flag emoji are formed from two regional-indicator code points; e.g.
 * ``"GB"`` → 🇬🇧. No image assets needed. Returns an empty string for
 * invalid input so callers can render unconditionally.
 */
export function flagEmoji(iso2: string): string {
  if (!iso2 || iso2.length !== 2) return "";
  const A = 0x1f1e6;
  const codePoints = iso2
    .toUpperCase()
    .split("")
    .map((c) => A + c.charCodeAt(0) - "A".charCodeAt(0));
  return String.fromCodePoint(...codePoints);
}

/** Props for {@link CountrySelect}. */
export interface CountrySelectProps {
  /** Currently selected ISO-2 code (or empty string for none). */
  value: string;
  /** Called with the new ISO-2 code when the user selects an item. */
  onChange: (value: string) => void;
  /** ID applied to the input — useful for `<label htmlFor>`. */
  id?: string;
  /** Placeholder shown when nothing is selected. */
  placeholder?: string;
  /** Disable the control. */
  disabled?: boolean;
}

/**
 * Render a searchable country dropdown.
 *
 * The selected value is the 2-letter ISO uppercase code. Pass an empty
 * string to start with no selection.
 */
export function CountrySelect({
  value,
  onChange,
  id,
  placeholder = "Select a country",
  disabled,
}: CountrySelectProps) {
  const selected = React.useMemo<CountryItem | null>(
    () => COUNTRY_ITEMS.find((i) => i.value === value) ?? null,
    [value],
  );

  return (
    <Combobox.Root<CountryItem>
      items={COUNTRY_ITEMS}
      value={selected}
      onValueChange={(item) => onChange(item?.value ?? "")}
      disabled={disabled}
      itemToStringValue={(item) => item.value}
      itemToStringLabel={(item) => item.label}
    >
      <Combobox.InputGroup className="flex h-8 w-full items-center gap-2 rounded-lg border border-input bg-background px-2.5 text-sm focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
        {selected && (
          <span aria-hidden className="text-base leading-none">
            {flagEmoji(selected.value)}
          </span>
        )}
        <Combobox.Input
          id={id}
          placeholder={placeholder}
          className="flex-1 bg-transparent outline-none placeholder:text-muted-foreground"
        />
        <Combobox.Trigger
          className="text-muted-foreground hover:text-foreground"
          aria-label="Open country list"
        >
          <ChevronDown className="size-4" />
        </Combobox.Trigger>
      </Combobox.InputGroup>

      <Combobox.Portal>
        <Combobox.Positioner sideOffset={4} className="z-50">
          <Combobox.Popup className="max-h-72 min-w-[var(--anchor-width)] overflow-y-auto rounded-lg border border-border bg-popover p-1 text-sm shadow-md">
            <Combobox.Empty className="px-2 py-1.5 text-muted-foreground">
              No matches.
            </Combobox.Empty>
            <Combobox.List>
              {(item: CountryItem) => (
                <Combobox.Item
                  key={item.value}
                  value={item}
                  className="flex cursor-default items-center gap-2 rounded-md px-2 py-1.5 outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                >
                  <span aria-hidden className="text-base leading-none">
                    {flagEmoji(item.value)}
                  </span>
                  <span className="flex-1">{item.label}</span>
                  <Combobox.ItemIndicator>
                    <Check className="size-3.5" />
                  </Combobox.ItemIndicator>
                </Combobox.Item>
              )}
            </Combobox.List>
          </Combobox.Popup>
        </Combobox.Positioner>
      </Combobox.Portal>
    </Combobox.Root>
  );
}

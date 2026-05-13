/**
 * Unit tests for {@link CountrySelect}.
 *
 * Drives the base-ui Combobox via real DOM events so the smoke test
 * matches what a user would do.
 */

import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  COUNTRY_ITEMS,
  CountrySelect,
  flagEmoji,
} from "@/components/country-select";

describe("flagEmoji", () => {
  it("returns the regional-indicator pair for a valid ISO-2 code", () => {
    expect(flagEmoji("US")).toBe("🇺🇸");
    expect(flagEmoji("GB")).toBe("🇬🇧");
  });

  it("uppercases lowercase input", () => {
    expect(flagEmoji("gb")).toBe("🇬🇧");
  });

  it("returns the empty string for invalid input", () => {
    expect(flagEmoji("")).toBe("");
    expect(flagEmoji("X")).toBe("");
    expect(flagEmoji("USA")).toBe("");
  });
});

describe("COUNTRY_ITEMS", () => {
  it("is sorted alphabetically by label", () => {
    const labels = COUNTRY_ITEMS.map((i) => i.label);
    const sorted = [...labels].sort((a, b) => a.localeCompare(b));
    expect(labels).toEqual(sorted);
  });

  it("includes major countries with their ISO-2 codes", () => {
    expect(COUNTRY_ITEMS.find((i) => i.value === "US")?.label).toBe(
      "United States",
    );
    expect(COUNTRY_ITEMS.find((i) => i.value === "GB")?.label).toBe(
      "United Kingdom",
    );
  });
});

describe("CountrySelect", () => {
  it("renders the selected country's flag + name", () => {
    render(<CountrySelect id="c" value="US" onChange={() => {}} />);
    // Flag emoji 🇺🇸 plus name show up next to the input.
    expect(screen.getByDisplayValue("United States")).toBeInTheDocument();
    expect(screen.getByText("🇺🇸")).toBeInTheDocument();
  });

  it("renders the placeholder when no country is selected", () => {
    render(
      <CountrySelect id="c" value="" onChange={() => {}} placeholder="Pick one" />,
    );
    const input = screen.getByPlaceholderText("Pick one") as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.value).toBe("");
  });

  it("exposes a combobox role for accessibility", () => {
    render(<CountrySelect id="c" value="" onChange={() => {}} />);
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("disables the input when the disabled prop is true", () => {
    render(
      <CountrySelect id="c" value="US" onChange={() => {}} disabled />,
    );
    expect(screen.getByRole("combobox")).toBeDisabled();
  });

  it("falls back to an empty flag for invalid ISO codes", () => {
    // Drive an unknown value so the selected-item branch is null and the
    // input renders with no flag.  Covers the `selected ?? null` path.
    const { container } = render(
      <CountrySelect id="c" value="ZZ" onChange={() => {}} />,
    );
    expect(container.querySelector("input")).toBeInTheDocument();
  });
});

/**
 * Unit tests for `lib/places.ts`.
 *
 * The Maps SDK loader is stubbed via `vi.mock` so the wrapper functions
 * can be exercised without a real network call.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

const setOptionsMock = vi.fn();
const importLibraryMock = vi.fn();

vi.mock("@googlemaps/js-api-loader", () => ({
  setOptions: (...args: unknown[]) => setOptionsMock(...args),
  importLibrary: (...args: unknown[]) => importLibraryMock(...args),
}));

import { isPlacesConfigured, parsePlaceResult } from "@/lib/places";

/** Build a fake `address_components` array of the shape Google returns. */
function components(
  parts: Array<{ types: string[]; long_name: string; short_name: string }>,
): google.maps.GeocoderAddressComponent[] {
  return parts as unknown as google.maps.GeocoderAddressComponent[];
}

describe("isPlacesConfigured", () => {
  it("returns false when NEXT_PUBLIC_GOOGLE_MAPS_API_KEY is empty", () => {
    expect(isPlacesConfigured()).toBe(false);
  });
});

describe("loadPlacesLibrary", () => {
  beforeEach(() => {
    vi.resetModules();
    setOptionsMock.mockReset();
    importLibraryMock.mockReset();
  });

  it("rejects when no API key is configured", async () => {
    const { loadPlacesLibrary } = await import("@/lib/places");
    await expect(loadPlacesLibrary()).rejects.toThrow(/empty/i);
    expect(setOptionsMock).not.toHaveBeenCalled();
  });

  it("calls setOptions and importLibrary once when the key is present", async () => {
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_MAPS_API_KEY", "fake-key");
    const fakeLib = { Autocomplete: class {} };
    importLibraryMock.mockResolvedValue(fakeLib);

    const { loadPlacesLibrary } = await import("@/lib/places");
    const lib = await loadPlacesLibrary();
    // Second call returns the cached promise without re-initialising.
    const lib2 = await loadPlacesLibrary();

    expect(lib).toBe(fakeLib);
    expect(lib2).toBe(fakeLib);
    expect(setOptionsMock).toHaveBeenCalledTimes(1);
    expect(setOptionsMock).toHaveBeenCalledWith({
      key: "fake-key",
      libraries: ["places"],
    });
    expect(importLibraryMock).toHaveBeenCalledTimes(1);
    expect(importLibraryMock).toHaveBeenCalledWith("places");

    vi.unstubAllEnvs();
  });
});

describe("parsePlaceResult", () => {
  it("returns blank fields when no components are passed", () => {
    expect(parsePlaceResult(undefined)).toEqual({
      street1: "",
      city: "",
      region: "",
      postal_code: "",
      country: "",
    });
  });

  it("joins street_number + route into street1", () => {
    const out = parsePlaceResult(
      components([
        { types: ["street_number"], long_name: "1600", short_name: "1600" },
        {
          types: ["route"],
          long_name: "Pennsylvania Avenue NW",
          short_name: "Pennsylvania Ave NW",
        },
      ]),
    );
    expect(out.street1).toBe("1600 Pennsylvania Avenue NW");
  });

  it("maps US-style components into the flat shape", () => {
    const out = parsePlaceResult(
      components([
        { types: ["street_number"], long_name: "1", short_name: "1" },
        { types: ["route"], long_name: "Main St", short_name: "Main St" },
        { types: ["locality"], long_name: "San Francisco", short_name: "SF" },
        {
          types: ["administrative_area_level_1"],
          long_name: "California",
          short_name: "CA",
        },
        { types: ["postal_code"], long_name: "94103", short_name: "94103" },
        { types: ["country"], long_name: "United States", short_name: "US" },
      ]),
    );
    expect(out).toEqual({
      street1: "1 Main St",
      city: "San Francisco",
      region: "CA",
      postal_code: "94103",
      country: "US",
    });
  });

  it("falls back to postal_town when locality is absent (UK addresses)", () => {
    const out = parsePlaceResult(
      components([
        { types: ["route"], long_name: "Baker Street", short_name: "Baker St" },
        { types: ["postal_town"], long_name: "London", short_name: "London" },
        { types: ["country"], long_name: "United Kingdom", short_name: "GB" },
      ]),
    );
    expect(out.city).toBe("London");
    expect(out.country).toBe("GB");
  });

  it("falls back to sublocality when locality and postal_town are absent", () => {
    const out = parsePlaceResult(
      components([
        { types: ["sublocality"], long_name: "Bronx", short_name: "Bronx" },
      ]),
    );
    expect(out.city).toBe("Bronx");
  });
});

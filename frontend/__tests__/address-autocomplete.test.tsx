/**
 * Unit tests for {@link AddressAutocomplete}.
 *
 * The `lib/places` module is mocked so we can control whether the
 * component sees a configured key, what the loader resolves to, and
 * fire fake `place_changed` events.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, waitFor } from "@testing-library/react";

const isPlacesConfiguredMock = vi.fn();
const loadPlacesLibraryMock = vi.fn();
const parsePlaceResultMock = vi.fn();

vi.mock("@/lib/places", () => ({
  isPlacesConfigured: () => isPlacesConfiguredMock(),
  loadPlacesLibrary: () => loadPlacesLibraryMock(),
  parsePlaceResult: (c: unknown) => parsePlaceResultMock(c),
}));

import { AddressAutocomplete } from "@/components/address-autocomplete";

/** Spin up a fake `places.Autocomplete` we can drive in tests. */
function buildFakePlacesLibrary() {
  let placeChangedHandler: (() => void) | null = null;
  let pendingPlace: { address_components?: unknown } = {};

  class FakeAutocomplete {
    addListener(event: string, handler: () => void) {
      if (event === "place_changed") placeChangedHandler = handler;
    }
    getPlace() {
      return pendingPlace;
    }
  }

  return {
    library: { Autocomplete: FakeAutocomplete } as unknown as google.maps.PlacesLibrary,
    fire: (place: { address_components?: unknown }) => {
      pendingPlace = place;
      placeChangedHandler?.();
    },
  };
}

beforeEach(() => {
  isPlacesConfiguredMock.mockReset();
  loadPlacesLibraryMock.mockReset();
  parsePlaceResultMock.mockReset();
  // Prevent the cleanup `google.maps.event.clearInstanceListeners` call
  // from blowing up — provide a minimal stub on the global.
  (globalThis as unknown as { google?: unknown }).google = {
    maps: { event: { clearInstanceListeners: () => {} } },
  };
});

describe("AddressAutocomplete", () => {
  it("renders nothing when no API key is configured", () => {
    isPlacesConfiguredMock.mockReturnValue(false);
    const { container } = render(<AddressAutocomplete onSelect={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("calls onSelect with the parsed address when the user picks a place", async () => {
    isPlacesConfiguredMock.mockReturnValue(true);
    const fake = buildFakePlacesLibrary();
    loadPlacesLibraryMock.mockResolvedValue(fake.library);
    parsePlaceResultMock.mockReturnValue({
      street1: "1 Main St",
      city: "San Francisco",
      region: "CA",
      postal_code: "94103",
      country: "US",
    });

    const onSelect = vi.fn();
    render(<AddressAutocomplete onSelect={onSelect} />);

    // Wait for loadPlacesLibrary().then(...) to wire up the listener.
    await waitFor(() => expect(loadPlacesLibraryMock).toHaveBeenCalledTimes(1));

    // Fire a fake place_changed event.
    await act(async () => {
      fake.fire({
        address_components: [{ types: ["route"], long_name: "Main St" }],
      });
    });

    expect(parsePlaceResultMock).toHaveBeenCalledWith([
      { types: ["route"], long_name: "Main St" },
    ]);
    expect(onSelect).toHaveBeenCalledWith({
      street1: "1 Main St",
      city: "San Francisco",
      region: "CA",
      postal_code: "94103",
      country: "US",
    });
  });

  it("renders an inline error when the loader rejects", async () => {
    isPlacesConfiguredMock.mockReturnValue(true);
    loadPlacesLibraryMock.mockRejectedValue(new Error("boom"));
    const onSelect = vi.fn();
    const { findByText } = render(
      <AddressAutocomplete onSelect={onSelect} />,
    );
    expect(await findByText(/boom/i)).toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
  });
});

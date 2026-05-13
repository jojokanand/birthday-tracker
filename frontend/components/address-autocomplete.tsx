/**
 * Google Places-powered address autocomplete input.
 *
 * Renders an input that, when typed into, shows Google's Places
 * suggestions; selecting one fires {@link AddressAutocompleteProps.onSelect}
 * with the parsed address. The user can still type and edit every
 * downstream field by hand — this control writes once and steps out of
 * the way.
 *
 * The component degrades to a plain hint when no API key is configured
 * (local dev, E2E, etc.) so the rest of the form stays usable.
 *
 * @module
 */

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  isPlacesConfigured,
  loadPlacesLibrary,
  parsePlaceResult,
  type ParsedAddress,
} from "@/lib/places";

/** Props for {@link AddressAutocomplete}. */
export interface AddressAutocompleteProps {
  /**
   * Called once when the user picks a suggestion. The form should
   * populate every address field from the resulting object; nothing
   * else in this component touches the form state.
   */
  onSelect: (parsed: ParsedAddress) => void;
}

/**
 * Render a Places Autocomplete input above the manual address fields.
 *
 * When the Maps key is missing, the component renders nothing rather
 * than a broken input — the manual fields below it remain usable.
 */
export function AddressAutocomplete({ onSelect }: AddressAutocompleteProps) {
  const [ready, setReady] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const acRef = React.useRef<google.maps.places.Autocomplete | null>(null);

  React.useEffect(() => {
    if (!isPlacesConfigured()) return;
    let cancelled = false;
    loadPlacesLibrary()
      .then((places) => {
        if (cancelled || !inputRef.current) return;
        const ac = new places.Autocomplete(inputRef.current, {
          types: ["address"],
          fields: ["address_components"],
        });
        ac.addListener("place_changed", () => {
          const place = ac.getPlace();
          const parsed = parsePlaceResult(place.address_components);
          onSelect(parsed);
          // Clear the autocomplete input so the user knows the value
          // landed in the fields below.
          if (inputRef.current) inputRef.current.value = "";
        });
        acRef.current = ac;
        setReady(true);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Maps API failed to load");
      });
    return () => {
      cancelled = true;
      if (acRef.current) {
        google.maps.event.clearInstanceListeners(acRef.current);
        acRef.current = null;
      }
    };
  }, [onSelect]);

  if (!isPlacesConfigured()) {
    return null;
  }

  return (
    <div className="space-y-1">
      <Label htmlFor="address-autocomplete">
        Search address{" "}
        <span className="text-muted-foreground font-normal">(optional)</span>
      </Label>
      <Input
        id="address-autocomplete"
        ref={inputRef}
        type="text"
        placeholder={ready ? "Start typing an address…" : "Loading…"}
        autoComplete="off"
      />
      {error && (
        <p className="text-destructive text-xs">
          Address suggestions unavailable: {error}
        </p>
      )}
    </div>
  );
}

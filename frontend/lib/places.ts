/**
 * Google Places-related helpers.
 *
 * Uses the modern functional API from `@googlemaps/js-api-loader`
 * (`setOptions` + `importLibrary`) so the SDK is fetched lazily and only
 * the libraries we need (`places`) are loaded. The module guards itself
 * when no API key is configured so the form stays usable in dev / E2E
 * without a real Google project.
 *
 * @module
 */

import { setOptions, importLibrary } from "@googlemaps/js-api-loader";

/** Parsed address — shape compatible with the backend's ``Address`` model. */
export interface ParsedAddress {
  street1: string;
  city: string;
  region: string;
  postal_code: string;
  /** 2-letter ISO uppercase code (e.g. ``"US"``). */
  country: string;
}

/** Build-time-baked Maps API key. Empty when not configured. */
export const GOOGLE_MAPS_API_KEY =
  process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";

/** ``true`` when the key is present so callers can decide to render UI at all. */
export function isPlacesConfigured(): boolean {
  return Boolean(GOOGLE_MAPS_API_KEY);
}

let placesLibraryPromise: Promise<google.maps.PlacesLibrary> | null = null;

/**
 * Return a promise that resolves once the Places library is ready.
 *
 * The first call sets the loader's API key and triggers a single SDK
 * fetch; subsequent calls return the cached promise.
 *
 * @throws When no API key is configured. Call {@link isPlacesConfigured}
 *   first to avoid this.
 */
export function loadPlacesLibrary(): Promise<google.maps.PlacesLibrary> {
  if (!GOOGLE_MAPS_API_KEY) {
    return Promise.reject(
      new Error(
        "NEXT_PUBLIC_GOOGLE_MAPS_API_KEY is empty; Places autocomplete is disabled.",
      ),
    );
  }
  if (placesLibraryPromise) return placesLibraryPromise;
  setOptions({ key: GOOGLE_MAPS_API_KEY, libraries: ["places"] });
  placesLibraryPromise = importLibrary("places");
  return placesLibraryPromise;
}

/**
 * Convert a Google ``PlaceResult.address_components`` array into our flat
 * :class:`ParsedAddress` shape.
 *
 * Google groups components by type. The mapping here covers the common
 * cases for residential addresses; anything missing comes back as the
 * empty string so the user can fill it in manually.
 *
 * Exposed (rather than kept private) so unit tests can exercise it
 * without instantiating the Maps SDK.
 */
export function parsePlaceResult(
  components: google.maps.GeocoderAddressComponent[] | undefined,
): ParsedAddress {
  const empty: ParsedAddress = {
    street1: "",
    city: "",
    region: "",
    postal_code: "",
    country: "",
  };
  if (!components) return empty;

  const get = (type: string) =>
    components.find((c) => c.types.includes(type));

  const number = get("street_number")?.long_name ?? "";
  const route = get("route")?.long_name ?? "";

  return {
    street1: [number, route].filter(Boolean).join(" "),
    city:
      get("locality")?.long_name ??
      get("postal_town")?.long_name ??
      get("sublocality")?.long_name ??
      "",
    region: get("administrative_area_level_1")?.short_name ?? "",
    postal_code: get("postal_code")?.long_name ?? "",
    country: get("country")?.short_name ?? "",
  };
}

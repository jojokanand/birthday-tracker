/**
 * Reusable contact form (used by both create and edit dialogs).
 *
 * Pure presentation: it doesn't know about HTTP. The parent passes an
 * `onSubmit(body, helpers)` callback that performs the API call and
 * decides how to react to its result. The form re-uses the existing
 * `CountrySelect` and `AddressAutocomplete` components so behaviour
 * stays identical between Add and Edit flows.
 *
 * @module
 */

"use client";

import * as React from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import PhoneInput, { isValidPhoneNumber } from "react-phone-number-input";
import "react-phone-number-input/style.css";
import { Button } from "@/components/ui/button";
import { DialogClose } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AddressAutocomplete } from "@/components/address-autocomplete";
import { CountrySelect } from "@/components/country-select";
import type { ContactResponse } from "@/lib/format";

/** Current full year — used as the upper bound for the birth-year input. */
const CURRENT_YEAR = new Date().getFullYear();

/** Form schema. See in-line comments on the cross-field rules. */
const schema = z
  .object({
    full_name: z.string().min(1, "Required"),
    preferred_name: z.string().optional(),
    email: z.string().email("Invalid email").optional().or(z.literal("")),
    phone: z
      .string()
      .optional()
      .refine((v) => !v || isValidPhoneNumber(v), {
        message: "Enter a valid phone number",
      }),
    street1: z.string().optional(),
    street2: z.string().optional(),
    city: z.string().optional(),
    region: z.string().optional(),
    postal_code: z.string().optional(),
    country: z
      .string()
      .optional()
      .refine((v) => !v || /^[A-Za-z]{2}$/.test(v), {
        message: "2-letter ISO code (e.g. US, GB)",
      }),
    // All three birthday inputs are optional at the form level. The
    // cross-field rule below requires both month and day if either is
    // provided, and rejects impossible dates (Feb 29 in a non-leap
    // year, Apr 31, etc.).
    birth_month: z.number().int().min(1).max(12).optional(),
    birth_day: z.number().int().min(1).max(31).optional(),
    birth_year: z.number().int().min(1900).max(CURRENT_YEAR).optional(),
  })
  .refine((d) => d.email || d.phone, {
    message: "Provide at least one of email or phone",
    path: ["email"],
  })
  .refine(
    (d) => {
      // ``country`` defaults to ``"US"`` so its presence alone is not a
      // signal that the user wants to attach an address — only the
      // free-text fields are. If any of those are filled, require
      // street1 + city + country.
      const hasAddressIntent =
        d.street1 || d.street2 || d.city || d.region || d.postal_code;
      if (!hasAddressIntent) return true;
      return Boolean(d.street1 && d.city && d.country);
    },
    {
      message:
        "Address needs at least street, city, and country (or leave it blank)",
      path: ["street1"],
    },
  )
  .refine(
    (d) => {
      const m = d.birth_month;
      const dy = d.birth_day;
      const y = d.birth_year;
      const anySet = m !== undefined || dy !== undefined || y !== undefined;
      if (!anySet) return true;
      if (m === undefined || dy === undefined) return false;
      // Probe a real Date to reject impossible combinations such as
      // Feb 30 or Feb 29 in a non-leap year. When ``year`` is missing,
      // 2000 (a leap year) lets ``02-29`` through.
      const probeYear = y ?? 2000;
      const probe = new Date(probeYear, m - 1, dy);
      return probe.getMonth() === m - 1 && probe.getDate() === dy;
    },
    {
      message:
        "Birthday needs both month and day, and must be a real date.",
      path: ["birth_month"],
    },
  );

/** Validated form values (also the shape the form returns to its parent). */
export type ContactFormValues = z.infer<typeof schema>;

/** Shape of the body sent to `POST /contacts` and `PUT /contacts/{id}`. */
export interface ContactBody {
  full_name: string;
  preferred_name: string | null;
  email: string | null;
  phone: string | null;
  address: {
    street1: string;
    street2: string | null;
    city: string;
    region: string | null;
    postal_code: string | null;
    country: string;
  } | null;
  birthday: {
    month: number;
    day: number;
    year: number | null;
  } | null;
}

/**
 * Translate validated form values into the API body.
 *
 * The defaulted ``country: "US"`` alone does not count as the user
 * wanting an address — they have to fill in at least one free-text
 * field for an Address to be attached.
 */
export function buildBody(values: ContactFormValues): ContactBody {
  const hasAddressIntent =
    values.street1 ||
    values.street2 ||
    values.city ||
    values.region ||
    values.postal_code;
  return {
    full_name: values.full_name,
    preferred_name: values.preferred_name || null,
    email: values.email || null,
    phone: values.phone || null,
    address: hasAddressIntent
      ? {
          street1: values.street1 ?? "",
          street2: values.street2 || null,
          city: values.city ?? "",
          region: values.region || null,
          postal_code: values.postal_code || null,
          country: (values.country ?? "").toUpperCase(),
        }
      : null,
    birthday:
      values.birth_month !== undefined && values.birth_day !== undefined
        ? {
            month: values.birth_month,
            day: values.birth_day,
            year: values.birth_year ?? null,
          }
        : null,
  };
}

/**
 * Build the form's default values from an existing contact.
 *
 * Used by the Edit dialog to pre-populate the inputs.  Address is
 * flattened to top-level fields so they line up with the schema.
 */
export function defaultsFromContact(c: ContactResponse): Partial<ContactFormValues> {
  return {
    full_name: c.full_name,
    preferred_name: c.preferred_name ?? "",
    email: c.email ?? "",
    phone: c.phone ?? "",
    street1: c.address?.street1 ?? "",
    street2: c.address?.street2 ?? "",
    city: c.address?.city ?? "",
    region: c.address?.region ?? "",
    postal_code: c.address?.postal_code ?? "",
    country: c.address?.country ?? "US",
    birth_month: c.birthday?.month,
    birth_day: c.birthday?.day,
    birth_year: c.birthday?.year ?? undefined,
  };
}

/** Props for {@link ContactForm}. */
export interface ContactFormProps {
  /** Initial values; defaults to a blank form (US country). */
  defaults?: Partial<ContactFormValues>;
  /** Submit-button label. Defaults to "Save". */
  submitLabel?: string;
  /**
   * Called with the API-shaped body when the user submits a valid form.
   *
   * Should return ``null`` on success, or an error message to render at
   * the bottom of the form when the server rejects the request.
   */
  onSubmit: (body: ContactBody) => Promise<string | null>;
}

/** Render the contact form. */
export function ContactForm({
  defaults,
  submitLabel = "Save",
  onSubmit,
}: ContactFormProps) {
  const [serverError, setServerError] = React.useState<string | null>(null);
  // Open the address section by default when editing a contact that
  // already has an address — they almost certainly want to see those
  // values without an extra click.
  const addressInitiallyOpen = Boolean(
    defaults?.street1 || defaults?.city || defaults?.postal_code,
  );
  const [addressOpen, setAddressOpen] = React.useState(addressInitiallyOpen);
  const birthdayInitiallyOpen = Boolean(
    defaults?.birth_month !== undefined ||
      defaults?.birth_day !== undefined ||
      defaults?.birth_year !== undefined,
  );
  const [birthdayOpen, setBirthdayOpen] = React.useState(birthdayInitiallyOpen);

  const {
    register,
    handleSubmit,
    control,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<ContactFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { country: "US", ...defaults },
  });

  const fillAddressFromPlace = React.useCallback(
    (place: {
      street1: string;
      city: string;
      region: string;
      postal_code: string;
      country: string;
    }) => {
      setValue("street1", place.street1, { shouldValidate: true });
      setValue("city", place.city, { shouldValidate: true });
      setValue("region", place.region);
      setValue("postal_code", place.postal_code);
      if (place.country) {
        setValue("country", place.country.toUpperCase(), {
          shouldValidate: true,
        });
      }
      setAddressOpen(true);
    },
    [setValue],
  );

  async function _onSubmit(values: ContactFormValues) {
    setServerError(null);
    const error = await onSubmit(buildBody(values));
    if (error) setServerError(error);
  }

  return (
    <form onSubmit={handleSubmit(_onSubmit)} className="space-y-4">
      <div className="space-y-1">
        <Label htmlFor="full_name">Full name *</Label>
        <Input id="full_name" {...register("full_name")} />
        {errors.full_name && (
          <p className="text-destructive text-xs">{errors.full_name.message}</p>
        )}
      </div>
      <div className="space-y-1">
        <Label htmlFor="preferred_name">Preferred name</Label>
        <Input id="preferred_name" {...register("preferred_name")} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" {...register("email")} />
        {errors.email && (
          <p className="text-destructive text-xs">{errors.email.message}</p>
        )}
      </div>
      <div className="space-y-1">
        <Label htmlFor="phone">Phone</Label>
        <Controller
          name="phone"
          control={control}
          render={({ field }) => (
            <PhoneInput
              id="phone"
              international
              defaultCountry="US"
              countryCallingCodeEditable={false}
              value={field.value}
              onChange={(v) => field.onChange(v ?? "")}
              numberInputProps={{
                className:
                  "flex h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
              }}
              className="flex items-center gap-2"
            />
          )}
        />
        {errors.phone && (
          <p className="text-destructive text-xs">{errors.phone.message}</p>
        )}
      </div>

      {/* --- Optional address section ------------------------------- */}
      <div className="border-t pt-3">
        <button
          type="button"
          onClick={() => setAddressOpen((v) => !v)}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          aria-expanded={addressOpen}
          aria-controls="address-section"
        >
          {addressOpen ? "− Hide address" : "+ Add address (optional)"}
        </button>

        {addressOpen && (
          <div id="address-section" className="mt-3 space-y-3">
            <AddressAutocomplete onSelect={fillAddressFromPlace} />
            <div className="space-y-1">
              <Label htmlFor="street1">Street address</Label>
              <Input id="street1" {...register("street1")} />
              {errors.street1 && (
                <p className="text-destructive text-xs">
                  {errors.street1.message}
                </p>
              )}
            </div>
            <div className="space-y-1">
              <Label htmlFor="street2">
                Apt / suite{" "}
                <span className="text-muted-foreground font-normal">
                  (optional)
                </span>
              </Label>
              <Input id="street2" {...register("street2")} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="city">City</Label>
                <Input id="city" {...register("city")} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="region">
                  State / region{" "}
                  <span className="text-muted-foreground font-normal">
                    (opt.)
                  </span>
                </Label>
                <Input id="region" {...register("region")} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="postal_code">
                  Postal code{" "}
                  <span className="text-muted-foreground font-normal">
                    (opt.)
                  </span>
                </Label>
                <Input id="postal_code" {...register("postal_code")} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="country">Country</Label>
                <Controller
                  name="country"
                  control={control}
                  render={({ field }) => (
                    <CountrySelect
                      id="country"
                      value={field.value ?? ""}
                      onChange={field.onChange}
                      placeholder="Select a country"
                    />
                  )}
                />
                {errors.country && (
                  <p className="text-destructive text-xs">
                    {errors.country.message}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* --- Optional birthday section ----------------------------- */}
      <div className="border-t pt-3">
        <button
          type="button"
          onClick={() => setBirthdayOpen((v) => !v)}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          aria-expanded={birthdayOpen}
          aria-controls="birthday-section"
        >
          {birthdayOpen ? "− Hide birthday" : "+ Add birthday (optional)"}
        </button>

        {birthdayOpen && (
          <div id="birthday-section" className="mt-3 grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label htmlFor="birth_month">Month</Label>
              <Input
                id="birth_month"
                type="number"
                min={1}
                max={12}
                placeholder="MM"
                {...register("birth_month", {
                  setValueAs: (v: string) =>
                    v === "" ? undefined : parseInt(v, 10),
                })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="birth_day">Day</Label>
              <Input
                id="birth_day"
                type="number"
                min={1}
                max={31}
                placeholder="DD"
                {...register("birth_day", {
                  setValueAs: (v: string) =>
                    v === "" ? undefined : parseInt(v, 10),
                })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="birth_year">
                Year{" "}
                <span className="text-muted-foreground font-normal">(opt.)</span>
              </Label>
              <Input
                id="birth_year"
                type="number"
                min={1900}
                max={CURRENT_YEAR}
                placeholder="YYYY"
                {...register("birth_year", {
                  setValueAs: (v: string) =>
                    v === "" ? undefined : parseInt(v, 10),
                })}
              />
            </div>
            {errors.birth_month && (
              <p className="text-destructive text-xs col-span-3">
                {errors.birth_month.message}
              </p>
            )}
          </div>
        )}
      </div>

      {serverError && <p className="text-destructive text-sm">{serverError}</p>}
      <div className="flex justify-end gap-2 pt-2">
        <DialogClose
          render={
            <Button variant="outline" type="button">
              Cancel
            </Button>
          }
        />
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}

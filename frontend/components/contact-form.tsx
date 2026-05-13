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

/** Form schema. See in-line comment on the address cross-field rule. */
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
  const initiallyOpen = Boolean(
    defaults?.street1 || defaults?.city || defaults?.postal_code,
  );
  const [addressOpen, setAddressOpen] = React.useState(initiallyOpen);

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

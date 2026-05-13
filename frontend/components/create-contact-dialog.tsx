/**
 * Dialog for creating a new contact via `POST /contacts`.
 *
 * Wraps `react-phone-number-input` for the country-code + number picker so
 * the owner doesn't need to type E.164 by hand, and exposes an optional
 * collapsible Address section (street1/2, city, region, postal, country)
 * matching the schema collected by the self-serve form.
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
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AddressAutocomplete } from "@/components/address-autocomplete";
import { CountrySelect } from "@/components/country-select";
import { useApiClient } from "@/lib/api-client";

/**
 * Form schema.  Phone is validated as a parseable E.164 string when present;
 * empty / undefined is allowed because the dialog also accepts email-only
 * contacts (the cross-field rule below requires at least one channel).
 */
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
      // street1 + city + country to keep us from persisting a half-built
      // address that's impossible to mail to.
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

type FormValues = z.infer<typeof schema>;

/** Build the API request body from validated form values. */
function buildBody(values: FormValues) {
  // Same rule as the validator: the defaulted country alone doesn't count
  // as the user wanting an address — they have to fill in at least one
  // free-text field for an Address to be attached.
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
 * Floating dialog containing the "Create contact" form.
 *
 * @param onCreated Invoked after a successful POST so the parent page can
 *   refresh its contact list.
 */
export function CreateContactDialog({
  onCreated,
}: {
  onCreated?: () => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [addressOpen, setAddressOpen] = React.useState(false);
  const api = useApiClient();

  const {
    register,
    handleSubmit,
    control,
    reset,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { country: "US" },
  });

  /** Push a Places result into the address fields without losing focus. */
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

  async function onSubmit(values: FormValues) {
    setServerError(null);
    const { error } = await api.POST("/contacts", { body: buildBody(values) });
    if (error) {
      setServerError("Failed to create contact. Please try again.");
      return;
    }
    reset({ country: "US" });
    setAddressOpen(false);
    setOpen(false);
    onCreated?.();
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button>Add contact</Button>} />
      <DialogContent showCloseButton>
        <DialogHeader>
          <DialogTitle>Add contact</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="full_name">Full name *</Label>
            <Input id="full_name" {...register("full_name")} />
            {errors.full_name && (
              <p className="text-destructive text-xs">
                {errors.full_name.message}
              </p>
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
              <p className="text-destructive text-xs">
                {errors.email.message}
              </p>
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
                  // Style the inner <input> to match shadcn's Input.
                  numberInputProps={{
                    className:
                      "flex h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
                  }}
                  className="flex items-center gap-2"
                />
              )}
            />
            {errors.phone && (
              <p className="text-destructive text-xs">
                {errors.phone.message}
              </p>
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

          {serverError && (
            <p className="text-destructive text-sm">{serverError}</p>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  Cancel
                </Button>
              }
            />
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

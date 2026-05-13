/**
 * Public self-serve form that contacts fill in to submit their details.
 *
 * @module
 */

"use client";

import * as React from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AddressAutocomplete } from "@/components/address-autocomplete";
import { CountrySelect } from "@/components/country-select";
import { apiClient } from "@/lib/api";

/**
 * Map a failed `POST /form/{token}` response to the message we render at
 * the bottom of the form.
 *
 * The backend wraps validation failures in problem+json with a top-level
 * `errors: [{loc, msg, type}]` array (see
 * `birthday_tracker.api.errors.validation_exception_handler`). For 422s
 * we surface the first message verbatim (stripping Pydantic's
 * `"Value error, "` prefix). Other statuses get fixed copy.
 */
export function messageForError(
  status: number | undefined,
  error: unknown,
): string {
  if (status === 410) {
    return "This form link has already been used or has expired.";
  }
  if (status === 404) {
    return "This form link is invalid. Please double-check the URL.";
  }
  if (status === 422) {
    const detail = extractValidationMessage(error);
    if (detail) return detail;
  }
  return "Something went wrong. Please try again.";
}

/**
 * Pull the first human-readable validation message out of a problem+json
 * error body. Returns `null` when the body has no usable message — in
 * that case the caller should fall back to a generic line.
 */
function extractValidationMessage(error: unknown): string | null {
  if (!error || typeof error !== "object") return null;
  const errors = (error as { errors?: unknown }).errors;
  if (!Array.isArray(errors) || errors.length === 0) return null;
  const first = errors[0];
  if (!first || typeof first !== "object") return null;
  const msg = (first as { msg?: unknown }).msg;
  if (typeof msg !== "string" || !msg.trim()) return null;
  // Pydantic prefixes `model_validator` failures with "Value error, ".
  // Strip it so the message reads naturally to the contact.
  return msg.replace(/^Value error,\s*/, "");
}

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const schema = z
  .object({
    full_name: z.string().min(1, "Required"),
    preferred_name: z.string().optional(),
    street1: z.string().min(1, "Required"),
    street2: z.string().optional(),
    city: z.string().min(1, "Required"),
    region: z.string().optional(),
    postal_code: z.string().optional(),
    country: z.string().length(2, "2-letter ISO code (e.g. US, GB)").toUpperCase(),
    birth_month: z.number({ message: "Required" }).int().min(1).max(12),
    birth_day: z.number({ message: "Required" }).int().min(1).max(31),
    birth_year: z
      .number()
      .int()
      .min(1900)
      .max(new Date().getFullYear())
      .optional(),
  })
  .superRefine((d, ctx) => {
    // Per-field rules above already flag missing/out-of-range values;
    // only run the cross-field real-date probe when month and day are
    // both present and individually valid. Probe with a leap year
    // (2000) when birth_year is omitted so 02-29 is allowed without a
    // year.
    const m = d.birth_month;
    const dy = d.birth_day;
    if (typeof m !== "number" || typeof dy !== "number") return;
    if (m < 1 || m > 12 || dy < 1 || dy > 31) return;
    const probeYear = d.birth_year ?? 2000;
    const probe = new Date(probeYear, m - 1, dy);
    if (probe.getMonth() !== m - 1 || probe.getDate() !== dy) {
      const monthLabel = MONTH_NAMES[m - 1] ?? `month ${m}`;
      const yearSuffix = d.birth_year ? ` in ${d.birth_year}` : "";
      ctx.addIssue({
        code: "custom",
        path: ["birthday"],
        message: `${monthLabel} ${dy} doesn't exist${yearSuffix}. Pick a valid date.`,
      });
    }
  });

type FormValues = z.infer<typeof schema>;

/** Props for {@link SelfServeForm}. */
export interface SelfServeFormProps {
  /** Raw form token from the URL. */
  token: string;
  /** Greeting name from the API (contact's preferred / first name). */
  greetingName: string;
}

/**
 * The form contacts use to submit their name, address, and birthday.
 *
 * Posts to `POST /form/{token}`.  On success shows a thank-you message.
 * On reuse/expiry shows a friendly error.
 */
export function SelfServeForm({ token, greetingName }: SelfServeFormProps) {
  const [submitted, setSubmitted] = React.useState(false);
  const [serverError, setServerError] = React.useState<string | null>(null);

  const {
    register,
    handleSubmit,
    control,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { country: "US" },
  });

  // Cross-field date error attaches to a synthetic ``birthday`` path so
  // it doesn't collide with the per-field "Required" / out-of-range
  // messages on month/day/year. react-hook-form stores it under the
  // same name; the type cast just acknowledges that it isn't a real
  // field on ``FormValues``.
  const birthdayError = (errors as Record<string, { message?: string }>)
    .birthday?.message;

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
    },
    [setValue],
  );

  async function onSubmit(values: FormValues) {
    setServerError(null);
    const { response, error } = await apiClient.POST("/form/{token}", {
      params: { path: { token } },
      body: {
        full_name: values.full_name,
        preferred_name: values.preferred_name || null,
        address: {
          street1: values.street1,
          street2: values.street2 || null,
          city: values.city,
          region: values.region || null,
          postal_code: values.postal_code || null,
          country: values.country,
        },
        birthday: {
          month: values.birth_month,
          day: values.birth_day,
          year: values.birth_year ?? null,
        },
      },
    });
    if (error) {
      setServerError(messageForError(response?.status, error));
      return;
    }
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <div className="flex flex-col items-center gap-4 py-12 text-center">
        <CheckCircle2 className="size-12 text-green-500" />
        <h2 className="text-xl font-semibold">Thank you, {greetingName}!</h2>
        <p className="text-muted-foreground text-sm max-w-sm">
          Your details have been saved. You can close this page.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <section className="space-y-4">
        <h2 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
          Your name
        </h2>
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
          <Label htmlFor="preferred_name">
            Preferred name{" "}
            <span className="text-muted-foreground font-normal">(optional)</span>
          </Label>
          <Input
            id="preferred_name"
            placeholder="What should we call you?"
            {...register("preferred_name")}
          />
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
          Mailing address
        </h2>
        <AddressAutocomplete onSelect={fillAddressFromPlace} />
        <div className="space-y-1">
          <Label htmlFor="street1">Street address *</Label>
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
            <span className="text-muted-foreground font-normal">(optional)</span>
          </Label>
          <Input id="street2" {...register("street2")} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label htmlFor="city">City *</Label>
            <Input id="city" {...register("city")} />
            {errors.city && (
              <p className="text-destructive text-xs">{errors.city.message}</p>
            )}
          </div>
          <div className="space-y-1">
            <Label htmlFor="region">
              State / region{" "}
              <span className="text-muted-foreground font-normal">(opt.)</span>
            </Label>
            <Input id="region" {...register("region")} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="postal_code">
              Postal code{" "}
              <span className="text-muted-foreground font-normal">(opt.)</span>
            </Label>
            <Input id="postal_code" {...register("postal_code")} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="country">Country *</Label>
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
      </section>

      <section className="space-y-4">
        <h2 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
          Birthday
        </h2>
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1">
            <Label htmlFor="birth_month">Month *</Label>
            <Input
              id="birth_month"
              type="number"
              min={1}
              max={12}
              placeholder="MM"
              {...register("birth_month", { valueAsNumber: true })}
            />
            {errors.birth_month && (
              <p className="text-destructive text-xs">
                {errors.birth_month.message}
              </p>
            )}
          </div>
          <div className="space-y-1">
            <Label htmlFor="birth_day">Day *</Label>
            <Input
              id="birth_day"
              type="number"
              min={1}
              max={31}
              placeholder="DD"
              {...register("birth_day", { valueAsNumber: true })}
            />
            {errors.birth_day && (
              <p className="text-destructive text-xs">
                {errors.birth_day.message}
              </p>
            )}
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
              max={new Date().getFullYear()}
              placeholder="YYYY"
              {...register("birth_year", {
                setValueAs: (v: string) => v === "" ? undefined : parseInt(v, 10),
              })}
            />
          </div>
        </div>
        {/* Cross-field date error (e.g. Feb 29 in a non-leap year). */}
        {birthdayError && (
          <p className="text-destructive text-xs">{birthdayError}</p>
        )}
      </section>

      {serverError && (
        <p className="text-destructive text-sm">{serverError}</p>
      )}

      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? "Submitting…" : "Submit"}
      </Button>
    </form>
  );
}

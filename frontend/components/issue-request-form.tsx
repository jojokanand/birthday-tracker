/**
 * Client-side form for issuing a collection request to a contact.
 *
 * @module
 */

"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ClipboardCopy, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api";
import type { ContactResponse } from "@/lib/format";

const schema = z.object({
  contact_id: z.string().uuid("Select a contact"),
  channel: z.enum(["email", "sms"]),
  destination: z.string().min(1, "Required"),
});

type FormValues = z.infer<typeof schema>;

/** Props for {@link IssueRequestForm}. */
export interface IssueRequestFormProps {
  /** All available contacts to choose from. */
  contacts: ContactResponse[];
  /** Pre-selected contact ID (from query param, optional). */
  initialContactId?: string;
}

/**
 * Form that lets the owner select a contact, pick a delivery channel, enter
 * the destination, and POST to `/collection-requests` to get a form URL.
 *
 * On success the generated form URL is displayed and can be copied.
 */
export function IssueRequestForm({
  contacts,
  initialContactId,
}: IssueRequestFormProps) {
  const [formUrl, setFormUrl] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);
  const [serverError, setServerError] = React.useState<string | null>(null);

  const selectedContact = contacts.find(
    (c) => c.id === initialContactId,
  );

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      contact_id: initialContactId ?? "",
      channel: selectedContact?.email ? "email" : "sms",
      destination: selectedContact?.email ?? selectedContact?.phone ?? "",
    },
  });

  const contactId = watch("contact_id");
  const channel = watch("channel");

  // Auto-fill destination when contact or channel changes.
  React.useEffect(() => {
    const contact = contacts.find((c) => c.id === contactId);
    if (!contact) return;
    setValue(
      "destination",
      channel === "email" ? (contact.email ?? "") : (contact.phone ?? ""),
    );
  }, [contactId, channel, contacts, setValue]);

  async function onSubmit(values: FormValues) {
    setServerError(null);
    setFormUrl(null);
    const { data, error } = await apiClient.POST("/collection-requests", {
      body: {
        contact_id: values.contact_id,
        channel: values.channel,
        destination: values.destination,
      },
    });
    if (error || !data) {
      setServerError("Failed to issue request. Is the contact ID valid?");
      return;
    }
    setFormUrl(data.form_url);
  }

  async function copyUrl() {
    if (!formUrl) return;
    await navigator.clipboard.writeText(formUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      {/* Contact selector */}
      <div className="space-y-1">
        <Label htmlFor="contact_id">Contact *</Label>
        <select
          id="contact_id"
          {...register("contact_id")}
          className="flex h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
        >
          <option value="">— select a contact —</option>
          {contacts.map((c) => (
            <option key={c.id} value={c.id}>
              {c.full_name}
              {c.preferred_name ? ` (${c.preferred_name})` : ""}
            </option>
          ))}
        </select>
        {errors.contact_id && (
          <p className="text-destructive text-xs">
            {errors.contact_id.message}
          </p>
        )}
      </div>

      {/* Channel */}
      <div className="space-y-1">
        <Label>Channel *</Label>
        <div className="flex gap-3">
          {(["email", "sms"] as const).map((ch) => (
            <label key={ch} className="flex items-center gap-1.5 text-sm cursor-pointer">
              <input
                type="radio"
                value={ch}
                {...register("channel")}
                className="accent-primary"
              />
              {ch === "email" ? "Email" : "SMS"}
            </label>
          ))}
        </div>
      </div>

      {/* Destination */}
      <div className="space-y-1">
        <Label htmlFor="destination">
          {channel === "email" ? "Email address" : "Phone number"} *
        </Label>
        <Input
          id="destination"
          type={channel === "email" ? "email" : "tel"}
          {...register("destination")}
        />
        {errors.destination && (
          <p className="text-destructive text-xs">
            {errors.destination.message}
          </p>
        )}
      </div>

      {serverError && (
        <p className="text-destructive text-sm">{serverError}</p>
      )}

      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Generating…" : "Generate form link"}
      </Button>

      {/* Result */}
      {formUrl && (
        <div className="rounded-lg border bg-muted/50 p-4 space-y-2">
          <p className="text-sm font-medium">Form URL — send this to the contact:</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs break-all">{formUrl}</code>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={copyUrl}
            >
              {copied ? (
                <CheckCircle2 className="size-4 text-green-600" />
              ) : (
                <ClipboardCopy className="size-4" />
              )}
              {copied ? "Copied!" : "Copy"}
            </Button>
          </div>
        </div>
      )}
    </form>
  );
}

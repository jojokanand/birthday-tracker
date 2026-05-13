/**
 * Client-side form for issuing a collection request to a contact.
 *
 * Two submit modes:
 *
 * - **Generate form link** — mints a token and prints the URL for the
 *   owner to copy/paste manually. Matches the original behaviour.
 * - **Send via Email / SMS** — calls the same backend with `send=true`
 *   so the backend hands the link off to the matching notifier
 *   (Gmail / Twilio). On success the destination is masked in the
 *   confirmation; the URL stays available for the "they say they
 *   didn't receive it" case.
 *
 * @module
 */

"use client";

import * as React from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ClipboardCopy, CheckCircle2, Send } from "lucide-react";
import PhoneInput, { isValidPhoneNumber } from "react-phone-number-input";
import "react-phone-number-input/style.css";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApiClient } from "@/lib/api-client";
import type { ContactResponse } from "@/lib/format";

const schema = z
  .object({
    contact_id: z.string().uuid("Select a contact"),
    channel: z.enum(["email", "sms"]),
    destination: z.string().min(1, "Required"),
  })
  .refine(
    (d) =>
      d.channel !== "sms" ||
      (typeof d.destination === "string" && isValidPhoneNumber(d.destination)),
    {
      message: "Enter a valid phone number",
      path: ["destination"],
    },
  );

type FormValues = z.infer<typeof schema>;

/** Shape of the success state shown after a submit. */
interface Result {
  formUrl: string;
  channel: "email" | "sms";
  destination: string;
  sent: boolean;
}

/** Props for {@link IssueRequestForm}. */
export interface IssueRequestFormProps {
  /** All available contacts to choose from. */
  contacts: ContactResponse[];
  /** Pre-selected contact ID (from query param, optional). */
  initialContactId?: string;
}

/**
 * Mask an email or phone destination for display in the success state.
 *
 * - Emails: ``ada@example.com`` → ``a***@example.com`` (preserve the
 *   first character + the domain so the owner can spot a typo).
 * - Phones: ``+15555550123`` → ``(***) ***-0123`` (last four digits
 *   only — matches the convention every bank uses).
 *
 * Exported so the unit test can drive the same logic without re-mounting
 * the form.
 */
export function maskDestination(channel: "email" | "sms", value: string): string {
  if (channel === "email") {
    const [local, domain] = value.split("@");
    if (!local || !domain) return value;
    return `${local.charAt(0)}***@${domain}`;
  }
  const digits = value.replace(/\D+/g, "");
  const last4 = digits.slice(-4) || "****";
  return `(***) ***-${last4}`;
}

/**
 * Form that lets the owner pick a contact, channel, and destination,
 * then either generate a copyable link or fire the link off via the
 * matching notifier.
 */
export function IssueRequestForm({
  contacts,
  initialContactId,
}: IssueRequestFormProps) {
  const [result, setResult] = React.useState<Result | null>(null);
  const [copied, setCopied] = React.useState(false);
  const [serverError, setServerError] = React.useState<string | null>(null);
  // Tracks which of the two buttons is mid-flight so only that one
  // shows its loading label.
  const [pendingMode, setPendingMode] = React.useState<"generate" | "send" | null>(
    null,
  );
  const api = useApiClient();

  const selectedContact = contacts.find((c) => c.id === initialContactId);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    control,
    formState: { errors },
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

  // Auto-fill destination when contact or channel changes. Wraps the
  // setValue call in a function reference so the eslint
  // ``react-hook-form/watch`` rule doesn't flag the watch() reads.
  React.useEffect(() => {
    const contact = contacts.find((c) => c.id === contactId);
    if (!contact) return;
    setValue(
      "destination",
      channel === "email" ? (contact.email ?? "") : (contact.phone ?? ""),
    );
  }, [contactId, channel, contacts, setValue]);

  async function submit(values: FormValues, send: boolean) {
    setServerError(null);
    setResult(null);
    setPendingMode(send ? "send" : "generate");
    const { data, error, response } = await api.POST("/collection-requests", {
      body: {
        contact_id: values.contact_id,
        channel: values.channel,
        destination: values.destination,
        send,
      },
    });
    setPendingMode(null);
    if (error || !data) {
      setServerError(messageForError(response?.status, error));
      return;
    }
    setResult({
      formUrl: data.form_url,
      channel: values.channel,
      destination: values.destination,
      sent: data.sent,
    });
  }

  async function copyUrl() {
    if (!result) return;
    await navigator.clipboard.writeText(result.formUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const sendButtonLabel = channel === "email" ? "Send via Email" : "Send via SMS";

  return (
    <form className="space-y-5">
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
          <p className="text-destructive text-xs">{errors.contact_id.message}</p>
        )}
      </div>

      {/* Channel */}
      <div className="space-y-1">
        <Label>Channel *</Label>
        <div className="flex gap-3">
          {(["email", "sms"] as const).map((ch) => (
            <label
              key={ch}
              className="flex items-center gap-1.5 text-sm cursor-pointer"
            >
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

      {/* Destination — email input or PhoneInput depending on channel */}
      <div className="space-y-1">
        <Label htmlFor="destination">
          {channel === "email" ? "Email address" : "Phone number"} *
        </Label>
        {channel === "email" ? (
          <Input
            id="destination"
            type="email"
            {...register("destination")}
          />
        ) : (
          <Controller
            name="destination"
            control={control}
            render={({ field }) => (
              <PhoneInput
                id="destination"
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
        )}
        {errors.destination && (
          <p className="text-destructive text-xs">{errors.destination.message}</p>
        )}
      </div>

      {serverError && <p className="text-destructive text-sm">{serverError}</p>}

      {/* SMS sending is gated off until Twilio is provisioned end-to-
          end. The Generate button is the workaround — owner copies
          the link out and texts it themselves. Backend still accepts
          ``send=true`` for SMS, so re-enabling here is one diff. */}
      {channel === "sms" && (
        <p className="text-muted-foreground text-xs">
          SMS sending is temporarily disabled. Use{" "}
          <span className="font-medium">Generate form link</span> to
          mint a link you can text yourself.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={pendingMode !== null}
          onClick={handleSubmit((v) => submit(v, false))}
        >
          {pendingMode === "generate" ? "Generating…" : "Generate form link"}
        </Button>
        {channel === "email" && (
          <Button
            type="button"
            disabled={pendingMode !== null}
            onClick={handleSubmit((v) => submit(v, true))}
          >
            <Send className="size-4" aria-hidden />
            {pendingMode === "send" ? "Sending…" : sendButtonLabel}
          </Button>
        )}
      </div>

      {/* Result */}
      {result && (
        <div
          className="rounded-lg border bg-muted/50 p-4 space-y-2"
          data-testid="issue-result"
        >
          {result.sent ? (
            <p className="text-sm font-medium flex items-center gap-1.5">
              <CheckCircle2
                className="size-4 text-green-600"
                aria-hidden
              />
              Sent to{" "}
              <span className="font-mono">
                {maskDestination(result.channel, result.destination)}
              </span>
              .
            </p>
          ) : (
            <p className="text-sm font-medium">
              Form link — send this to the contact:
            </p>
          )}
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs break-all">{result.formUrl}</code>
            <Button type="button" variant="outline" size="sm" onClick={copyUrl}>
              {copied ? (
                <CheckCircle2 className="size-4 text-green-600" />
              ) : (
                <ClipboardCopy className="size-4" />
              )}
              {copied ? "Copied!" : "Copy"}
            </Button>
          </div>
          {result.sent && (
            <p className="text-muted-foreground text-xs">
              Keep this link handy in case the message doesn&apos;t reach the
              contact.
            </p>
          )}
        </div>
      )}
    </form>
  );
}

/**
 * Translate a failed `POST /collection-requests` response into a
 * user-friendly message rendered above the buttons.
 *
 * The backend returns problem+json with stable ``title`` / ``detail``
 * fields; surface ``detail`` when it's present so 502 / 503 / 422
 * paths read clearly.
 */
function messageForError(status: number | undefined, error: unknown): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  if (status === 503) {
    return "This delivery channel isn't configured on the server. Generate the link instead and send it yourself.";
  }
  if (status === 502) {
    return "The email/SMS provider rejected the send. Try again, or generate the link and deliver it manually.";
  }
  if (status === 404) {
    return "Contact not found. Pick a different contact and try again.";
  }
  return "Failed to issue request. Please try again.";
}

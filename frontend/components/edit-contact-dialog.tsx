/**
 * Dialog for editing an existing contact via `PUT /contacts/{id}`.
 *
 * Controlled — the parent owns `open` and `onOpenChange` so it can wire
 * a row-level pencil button as the trigger. Renders nothing when no
 * contact is supplied (the parent typically conditions the dialog on
 * the active row).
 *
 * @module
 */

"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ContactForm, defaultsFromContact } from "@/components/contact-form";
import { useApiClient } from "@/lib/api-client";
import type { ContactResponse } from "@/lib/format";

/** Props for {@link EditContactDialog}. */
export interface EditContactDialogProps {
  /** Contact being edited. ``null`` hides the dialog. */
  contact: ContactResponse | null;
  /** Whether the dialog is open. */
  open: boolean;
  /** Called when the dialog requests to open or close. */
  onOpenChange: (open: boolean) => void;
  /** Called after a successful save so the parent can refresh its list. */
  onSaved?: () => void;
}

/**
 * Edit-contact dialog.
 *
 * The form is remounted (via `key`) when ``contact`` changes so the
 * default values reset cleanly between rows.
 */
export function EditContactDialog({
  contact,
  open,
  onOpenChange,
  onSaved,
}: EditContactDialogProps) {
  const api = useApiClient();
  if (!contact) return null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton>
        <DialogHeader>
          <DialogTitle>Edit contact</DialogTitle>
        </DialogHeader>
        <ContactForm
          key={contact.id}
          defaults={defaultsFromContact(contact)}
          submitLabel="Save changes"
          onSubmit={async (body) => {
            const { error } = await api.PUT("/contacts/{contact_id}", {
              params: { path: { contact_id: contact.id } },
              body,
            });
            if (error) return "Failed to save changes. Please try again.";
            onOpenChange(false);
            onSaved?.();
            return null;
          }}
        />
      </DialogContent>
    </Dialog>
  );
}

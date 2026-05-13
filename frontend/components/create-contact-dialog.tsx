/**
 * Dialog for creating a new contact via `POST /contacts`.
 *
 * Renders the "Add contact" trigger and owns its own open state. The
 * actual form lives in {@link ContactForm}, which is shared with the
 * Edit dialog so behavior stays identical.
 *
 * @module
 */

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ContactForm } from "@/components/contact-form";
import { useApiClient } from "@/lib/api-client";

/**
 * Floating dialog containing the "Create contact" form.
 *
 * @param onCreated Invoked after a successful POST so the parent page
 *   can refresh its contact list.
 */
export function CreateContactDialog({
  onCreated,
}: {
  onCreated?: () => void;
}) {
  const [open, setOpen] = React.useState(false);
  const api = useApiClient();
  // Used to remount ContactForm on close so the next open starts fresh.
  const [resetKey, setResetKey] = React.useState(0);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setResetKey((k) => k + 1);
      }}
    >
      <DialogTrigger render={<Button>Add contact</Button>} />
      <DialogContent showCloseButton>
        <DialogHeader>
          <DialogTitle>Add contact</DialogTitle>
        </DialogHeader>
        <ContactForm
          key={resetKey}
          submitLabel="Save"
          onSubmit={async (body) => {
            const { error } = await api.POST("/contacts", { body });
            if (error) return "Failed to create contact. Please try again.";
            setOpen(false);
            onCreated?.();
            return null;
          }}
        />
      </DialogContent>
    </Dialog>
  );
}

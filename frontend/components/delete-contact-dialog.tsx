/**
 * Confirmation dialog for deleting a contact.
 *
 * Renders nothing when no contact is provided. Confirming calls
 * `DELETE /contacts/{id}` and signals the parent via `onDeleted` so it
 * can refresh the list. Errors keep the dialog open with an inline
 * message; cancel closes without an API call.
 *
 * @module
 */

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useApiClient } from "@/lib/api-client";
import type { ContactResponse } from "@/lib/format";

/** Props for {@link DeleteContactDialog}. */
export interface DeleteContactDialogProps {
  /** Contact slated for deletion. ``null`` hides the dialog. */
  contact: ContactResponse | null;
  /** Whether the dialog is open. */
  open: boolean;
  /** Called when the dialog requests to open or close. */
  onOpenChange: (open: boolean) => void;
  /** Called after a successful DELETE so the parent can refresh its list. */
  onDeleted?: () => void;
}

/** Render the delete-confirmation dialog. */
export function DeleteContactDialog({
  contact,
  open,
  onOpenChange,
  onDeleted,
}: DeleteContactDialogProps) {
  const api = useApiClient();
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  // The parent passes ``contact=null`` on close so this branch fully
  // unmounts the dialog — state resets naturally on the next open.
  if (!contact) return null;

  const displayName = contact.preferred_name
    ? `${contact.preferred_name} (${contact.full_name})`
    : contact.full_name;

  const handleConfirm = async () => {
    setError(null);
    setBusy(true);
    const { error: apiError } = await api.DELETE("/contacts/{contact_id}", {
      params: { path: { contact_id: contact.id } },
    });
    setBusy(false);
    if (apiError) {
      setError("Failed to delete contact. Please try again.");
      return;
    }
    onOpenChange(false);
    onDeleted?.();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton>
        <DialogHeader>
          <DialogTitle>Delete contact</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Delete <strong className="text-foreground">{displayName}</strong>?
          This can&apos;t be undone.
        </p>
        {error && <p className="text-destructive text-sm">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <DialogClose
            render={
              <Button variant="outline" type="button" disabled={busy}>
                Cancel
              </Button>
            }
          />
          <Button
            type="button"
            variant="destructive"
            onClick={handleConfirm}
            disabled={busy}
          >
            {busy ? "Deleting…" : "Delete"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

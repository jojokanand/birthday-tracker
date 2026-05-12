/**
 * Dialog for creating a new contact via `POST /contacts`.
 *
 * @module
 */

"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
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
import { apiClient } from "@/lib/api";

const schema = z
  .object({
    full_name: z.string().min(1, "Required"),
    preferred_name: z.string().optional(),
    email: z.string().email("Invalid email").optional().or(z.literal("")),
    phone: z.string().optional(),
  })
  .refine((d) => d.email || d.phone, {
    message: "Provide at least one of email or phone",
    path: ["email"],
  });

type FormValues = z.infer<typeof schema>;

/**
 * Floating dialog containing the "Create contact" form.
 *
 * On successful creation the page is refreshed via `router.refresh()` so the
 * contacts table picks up the new row without a full navigation.
 */
export function CreateContactDialog() {
  const [open, setOpen] = React.useState(false);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const router = useRouter();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setServerError(null);
    const { error } = await apiClient.POST("/contacts", {
      body: {
        full_name: values.full_name,
        preferred_name: values.preferred_name || null,
        email: values.email || null,
        phone: values.phone || null,
      },
    });
    if (error) {
      setServerError("Failed to create contact. Please try again.");
      return;
    }
    reset();
    setOpen(false);
    router.refresh();
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
            <Label htmlFor="phone">Phone (E.164)</Label>
            <Input id="phone" type="tel" {...register("phone")} />
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

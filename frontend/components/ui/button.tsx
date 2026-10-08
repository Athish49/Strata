import * as React from "react";
import { Slot } from "radix-ui";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-[8px] text-[14px] font-medium leading-5 transition-colors duration-150 ease-out disabled:pointer-events-none disabled:text-ink-4 [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:stroke-[1.5]",
  {
    variants: {
      variant: {
        primary: "bg-ink text-white hover:bg-[#2a2a28] disabled:bg-surface-muted",
        secondary: "border border-border-strong bg-surface text-ink hover:bg-surface-muted",
        ghost: "text-ink-2 hover:bg-surface-muted hover:text-ink",
      },
      size: {
        default: "h-9 px-3.5",
        sm: "h-8 px-3",
        icon: "size-8",
      },
    },
    defaultVariants: { variant: "secondary", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({ className, variant, size, asChild, type, ...props }: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button";
  return (
    <Comp
      type={asChild ? undefined : (type ?? "button")}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}

import { cva, type VariantProps } from "class-variance-authority";
import { Star } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

const btn = cva(
  "inline-flex items-center justify-center gap-2 rounded-full font-medium transition-all disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
  {
    variants: {
      variant: {
        primary: "bg-wine text-ivory hover:bg-oxblood shadow-[var(--shadow-paper)]",
        secondary: "bg-ivory text-wine border border-wine/40 hover:bg-beige",
        ghost: "text-wine hover:bg-wine/10",
        blue: "bg-dusty text-oxblood hover:bg-dusty/80",
        onWine: "bg-ivory text-wine hover:bg-beige",
      },
      size: { sm: "h-8 px-3 text-xs", md: "h-10 px-5 text-sm", lg: "h-12 px-7 text-base" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export function Btn({
  className,
  variant,
  size,
  ...p
}: ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof btn>) {
  return <button className={cn(btn({ variant, size }), className)} {...p} />;
}

const CO_STYLE = [
  "bg-wine text-ivory",
  "bg-dusty text-oxblood",
  "bg-oxblood text-beige",
  "bg-beige text-wine border border-wine/40",
  "bg-taupe text-ivory",
  "bg-ivory text-oxblood border border-dusty",
];
export function CO({ n, className }: { n: number; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-full px-2.5 font-mono text-[11px] font-medium",
        CO_STYLE[(n - 1) % 6],
        className,
      )}
    >
      CO{n}
    </span>
  );
}

export type Status =
  | "Draft"
  | "Approved"
  | "Rejected"
  | "Published"
  | "Closed"
  | "Processing"
  | "Done"
  | "Failed"
  | "On Track"
  | "Needs Work";
const ST: Record<Status, string> = {
  Draft: "border-taupe text-espresso",
  Approved: "border-success text-success",
  Rejected: "border-wine text-wine",
  Published: "border-wine bg-wine text-ivory",
  Closed: "border-taupe bg-taupe/20 text-muted-foreground",
  Processing: "border-warn text-warn",
  Done: "border-success text-success",
  Failed: "border-wine bg-wine/10 text-wine",
  "On Track": "border-success text-success",
  "Needs Work": "border-wine bg-wine/10 text-wine",
};
export function Chip({ s }: { s: Status }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium",
        ST[s],
      )}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {s}
    </span>
  );
}

export function PageHead({
  eyebrow,
  title,
  sub,
  right,
}: {
  eyebrow: string;
  title: ReactNode;
  sub?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="eyebrow flex items-center gap-2">
          <Star className="size-3 fill-wine text-wine" />
          {eyebrow}
        </div>
        <h1 className="display mt-2 text-5xl">{title}</h1>
        {sub && <p className="mt-2 max-w-xl text-sm text-muted-foreground">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function Card({
  className,
  children,
  title,
  action,
}: {
  className?: string;
  children: ReactNode;
  title?: string;
  action?: ReactNode;
}) {
  return (
    <section className={cn("paper p-6", className)}>
      {title && (
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-2xl font-semibold">{title}</h3>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Bar({
  v,
  target,
  tone = "wine",
}: {
  v: number;
  target?: number;
  tone?: "wine" | "blue";
}) {
  return (
    <div className="relative h-2.5 w-full rounded-full bg-beige">
      <div
        className={cn("h-full rounded-full", tone === "wine" ? "bg-wine" : "bg-dusty")}
        style={{ width: `${v}%` }}
      />
      {target && (
        <div className="absolute -top-1 h-4.5 w-0.5 bg-oxblood" style={{ left: `${target}%` }} />
      )}
    </div>
  );
}

export function Field({
  label,
  children,
  error,
}: {
  label: string;
  children: ReactNode;
  error?: string | undefined;
}) {
  return (
    <label className="block">
      <span className="eyebrow">{label}</span>
      <div className="mt-1.5">{children}</div>
      {error && <span className="mt-1 block text-xs text-wine">{error}</span>}
    </label>
  );
}
export const inputCls =
  "h-11 w-full rounded-full border border-input bg-ivory px-4 text-sm outline-none placeholder:text-muted-foreground/70 focus:border-wine focus:ring-2 focus:ring-wine/20";

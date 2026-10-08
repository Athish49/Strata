import { createElement } from "react";
import { icons, Circle } from "lucide-react";

type IconProps = { className?: string; strokeWidth?: number; "aria-hidden"?: boolean };

/** Renders a lucide icon by export name (the verdict-token maps store names). Falls back to a circle. */
export function NamedIcon({ name, ...props }: { name: string } & IconProps) {
  const Cmp = (icons as Record<string, React.ComponentType<IconProps>>)[name] ?? Circle;
  return createElement(Cmp, props);
}

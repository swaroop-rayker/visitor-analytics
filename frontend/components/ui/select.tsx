import * as React from "react";
import { cn } from "@/lib/utils";

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn("focus-ring h-9 rounded-md border bg-background px-3 text-sm", className)} {...props} />;
}


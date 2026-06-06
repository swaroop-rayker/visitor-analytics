import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(`${value}${value.endsWith("Z") ? "" : "Z"}`));
}

export function formatBytes(value: number) {
  if (!value) return "0 B";
  const unit = Math.floor(Math.log(value) / Math.log(1024));
  return `${(value / 1024 ** unit).toFixed(1)} ${["B", "KB", "MB", "GB"][unit]}`;
}


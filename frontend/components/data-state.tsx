import { AlertCircle, LoaderCircle } from "lucide-react";

export function LoadingState() {
  return <div className="flex min-h-48 items-center justify-center text-muted-foreground"><LoaderCircle className="mr-2 size-4 animate-spin" />Loading</div>;
}
export function ErrorState({ message }: { message: string }) {
  return <div className="flex min-h-48 items-center justify-center text-sm text-red-400"><AlertCircle className="mr-2 size-4" />{message}</div>;
}
export function EmptyState({ label = "No data yet" }: { label?: string }) {
  return <div className="flex min-h-40 items-center justify-center text-sm text-muted-foreground">{label}</div>;
}


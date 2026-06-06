import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function Confidence({ value }: { value: number }) {
  return (
    <Badge className={cn(
      value >= 75 ? "border-green-900 bg-green-950/40 text-green-400" :
      value >= 45 ? "border-amber-900 bg-amber-950/40 text-amber-400" :
      "border-zinc-700 text-zinc-400",
    )}>
      {value}% confidence
    </Badge>
  );
}


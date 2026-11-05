import { useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { productName, rupiah, tokenMatch } from "@/lib/format";
import { cn } from "@/lib/utils";

type Opt = { id: string; label: string; sub?: string; search: string };

export function SearchSelect({ options, value, onChange, placeholder, testid }: {
  options: Opt[]; value?: string | null; onChange: (id: string) => void; placeholder: string; testid: string;
}) {
  const [open, setOpen] = useState(false);
  const selected = options.find((o) => o.id === value);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" className="h-11 w-full justify-between bg-white font-normal" data-testid={testid}>
          <span className={cn("truncate", !selected && "text-slate-400")}>{selected ? selected.label : placeholder}</span>
          <ChevronsUpDown className="opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] min-w-[280px] p-0" align="start">
        <Command filter={(v, search) => {
          const o = options.find((x) => x.id === v);
          return o && tokenMatch(o.search, search) ? 1 : 0;
        }}>
          <CommandInput placeholder="Ketik untuk mencari..." data-testid={`${testid}-search`} />
          <CommandList>
            <CommandEmpty>Tidak ditemukan.</CommandEmpty>
            <CommandGroup>
              {options.map((o) => (
                <CommandItem key={o.id} value={o.id} onSelect={() => { onChange(o.id); setOpen(false); }} data-testid={`${testid}-option`}>
                  <Check className={cn("mr-1 h-4 w-4", value === o.id ? "opacity-100" : "opacity-0")} />
                  <div className="min-w-0">
                    <p className="truncate text-sm">{o.label}</p>
                    {o.sub && <p className="text-xs text-slate-500">{o.sub}</p>}
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export const productOptions = (products: any[]): Opt[] => products.filter((p) => p.is_active).map((p) => ({
  id: p.id, label: productName(p.name, p.voltage), sub: `${p.code} • ${rupiah(p.price)}`,
  search: `${p.code} ${productName(p.name, p.voltage)} ${p.voltage}`,
}));

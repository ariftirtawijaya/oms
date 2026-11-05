import { useState } from "react";
import { id as localeId } from "date-fns/locale";
import { CalendarDays } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ymdToDisplay } from "@/lib/format";

const toYmd = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const fromYmd = (s: string) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };

export function DateInput({ value, onChange, testid, placeholder = "Pilih tanggal" }: {
  value: string; onChange: (v: string) => void; testid: string; placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" className="h-11 w-full justify-start gap-2 bg-white font-normal tabular-nums" data-testid={testid}>
          <CalendarDays className="text-slate-400" />
          {value ? ymdToDisplay(value) : <span className="text-slate-400">{placeholder}</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar mode="single" locale={localeId} selected={value ? fromYmd(value) : undefined} defaultMonth={value ? fromYmd(value) : undefined}
          onSelect={(d: Date | undefined) => { if (d) { onChange(toYmd(d)); setOpen(false); } }} />
        {value && (
          <div className="border-t p-2">
            <Button size="sm" variant="ghost" className="w-full" onClick={() => { onChange(""); setOpen(false); }} data-testid={`${testid}-clear`}>Hapus tanggal</Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}

export function DateTimeInput({ value, onChange, testid }: { value: string; onChange: (v: string) => void; testid: string }) {
  const [date, time = ""] = value.split("T");
  const onTime = (raw: string) => {
    let s = raw.replace(/[^\d]/g, "").slice(0, 4);
    if (s.length > 2) s = `${s.slice(0, 2)}:${s.slice(2)}`;
    onChange(`${date || ""}T${s}`);
  };
  const timeInvalid = time.length > 0 && !/^([01]\d|2[0-3]):[0-5]\d$/.test(time);
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_120px]">
      <DateInput value={date || ""} onChange={(d) => onChange(`${d}T${time}`)} testid={`${testid}-date`} />
      <Input inputMode="numeric" placeholder="JJ:MM" maxLength={5} className={`h-11 tabular-nums ${timeInvalid ? "border-red-400" : ""}`}
        value={time} onChange={(e) => onTime(e.target.value)} aria-label="Jam (24 jam)" data-testid={`${testid}-time`} />
    </div>
  );
}

export const isValidDateTime = (v: string) => /^\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):[0-5]\d$/.test(v);

import { useCallback, useEffect, useState } from "react";
import { newKey } from "@/lib/format";

export type CartItem = {
  key: string;
  product_id?: string | null;
  custom_name?: string | null;
  code?: string;
  name: string;
  voltage?: string;
  price: number | null;
  qty: number;
};

type CartState = { items: CartItem[]; notes: string; idem: string };

export function useCart(storageKey: string) {
  const load = (): CartState => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) return JSON.parse(raw);
    } catch { /* ignore */ }
    return { items: [], notes: "", idem: newKey() };
  };
  const [state, setState] = useState<CartState>(load);

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(state));
  }, [state, storageKey]);

  const addProduct = useCallback((p: any, initialQty: number) => {
    setState((s) => {
      const ex = s.items.find((i) => i.product_id === p.id);
      if (ex) return { ...s, items: s.items.map((i) => (i.product_id === p.id ? { ...i, qty: i.qty + 1 } : i)) };
      return { ...s, items: [...s.items, { key: p.id, product_id: p.id, code: p.code, name: p.name, voltage: p.voltage, price: p.price, qty: initialQty }] };
    });
  }, []);

  const addCustom = useCallback((name: string, qty: number) => {
    setState((s) => {
      const ex = s.items.find((i) => !i.product_id && i.custom_name?.toLowerCase() === name.toLowerCase());
      if (ex) return { ...s, items: s.items.map((i) => (i === ex ? { ...i, qty: i.qty + qty } : i)) };
      return { ...s, items: [...s.items, { key: `custom-${newKey()}`, custom_name: name, name, voltage: "-", price: null, qty }] };
    });
  }, []);

  const setQty = useCallback((key: string, qty: number) => {
    setState((s) => ({ ...s, items: s.items.map((i) => (i.key === key ? { ...i, qty: Math.max(0, qty) } : i)) }));
  }, []);

  const remove = useCallback((key: string) => setState((s) => ({ ...s, items: s.items.filter((i) => i.key !== key) })), []);
  const setNotes = useCallback((notes: string) => setState((s) => ({ ...s, notes })), []);
  const updatePrices = useCallback((map: Record<string, number>) => {
    setState((s) => ({ ...s, items: s.items.map((i) => (i.product_id && map[i.product_id] !== undefined ? { ...i, price: map[i.product_id] } : i)) }));
  }, []);
  const clear = useCallback(() => setState({ items: [], notes: "", idem: newKey() }), []);

  const total = state.items.reduce((a, i) => a + (i.price ?? 0) * i.qty, 0);
  const totalQty = state.items.reduce((a, i) => a + i.qty, 0);
  return { ...state, total, totalQty, addProduct, addCustom, setQty, remove, setNotes, updatePrices, clear };
}

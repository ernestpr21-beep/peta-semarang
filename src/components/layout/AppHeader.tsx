import { Link, useRouterState } from "@tanstack/react-router";
import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";

const NAV = [
  { to: "/", label: "Peta" },
  { to: "/metodologi", label: "Metodologi" },
  { to: "/data-zona", label: "Data zona" },
  { to: "/tentang", label: "Tentang" },
] as const;

export function AppHeader() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const theme = useAppStore((s) => s.theme);
  const toggleTheme = useAppStore((s) => s.toggleTheme);
  return (
    <header className="relative z-30 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-surface/90 px-2 backdrop-blur-sm sm:gap-3 sm:px-4">
      <Link to="/" className="flex min-w-0 items-center gap-2 text-fg no-underline">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary font-mono text-[11px] font-semibold tracking-tight text-primary-foreground">SMG</span>
        <span className="hidden leading-tight min-[400px]:block">
          <span className="block whitespace-nowrap text-sm font-semibold tracking-tight">Peta Semarang</span>
          <span className="hidden text-[11px] text-fg-muted sm:block">Estimasi kisaran harga pasar tanah</span>
        </span>
      </Link>
      <nav className="ml-auto flex min-w-0 items-center gap-0 overflow-x-auto">
        {NAV.map((item) => {
          const active = pathname === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "whitespace-nowrap rounded-md px-1.5 py-1.5 text-[11px] font-medium no-underline transition-colors sm:px-2.5 sm:text-sm",
                active ? "bg-surface-2 text-fg" : "text-fg-muted hover:text-fg",
              )}
            >
              {item.label}
            </Link>
          );
        })}
        <button
          type="button"
          aria-label={theme === "dark" ? "Mode terang" : "Mode gelap"}
          title={theme === "dark" ? "Mode terang" : "Mode gelap"}
          onClick={toggleTheme}
          className="ml-1 flex size-9 shrink-0 items-center justify-center rounded-md hover:bg-surface-2"
        >
          {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>
      </nav>
    </header>
  );
}

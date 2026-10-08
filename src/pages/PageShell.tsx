import type { ReactNode } from "react";
export function PageShell({ title, lead, children, wide }: { title: string; lead?: ReactNode; children: ReactNode; wide?: boolean }) {
  return (
    <main className="flex-1 overflow-y-auto">
      <div className={`mx-auto px-4 py-8 sm:px-6 ${wide ? "max-w-5xl" : "max-w-3xl"}`}>
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight">{title}</h1>
        {lead ? <p className="mt-2 text-fg-muted">{lead}</p> : null}
        <div className="prose-id mt-4">{children}</div>
      </div>
    </main>
  );
}

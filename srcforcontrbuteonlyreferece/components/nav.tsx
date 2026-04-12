"use client";

import Link from "next/link";
import { useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { useEffect, useState } from "react";

export function Nav() {
  const { connected, publicKey } = useWallet();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <nav className="sticky top-0 z-40 border-b border-[color:var(--surface-border)] bg-[color:var(--surface)]/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-3">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[color:var(--olive-700)]">
            <span className="text-white text-sm font-bold">BB</span>
          </div>
          <span className="text-base font-bold tracking-tight text-[color:var(--ink)]">
            Blink<span className="text-[color:var(--olive-700)]">Bounties</span>
          </span>
        </Link>

        <div className="flex-1 max-w-xs">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[color:var(--ink-secondary)]/70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search raffles..."
              className="w-full rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] py-2 pl-9 pr-4 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--ink-secondary)]/70 focus:border-[color:var(--olive-500)] focus:bg-white focus:outline-none transition-colors"
            />
          </div>
        </div>

        <div className="ml-auto flex items-center gap-3">
          {connected && publicKey && (
            <div className="hidden items-center gap-2 rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] px-3 py-2 sm:flex">
              <div className="h-2 w-2 rounded-full bg-[color:var(--olive-500)]" />
              <span className="font-mono text-sm text-[color:var(--ink-secondary)]">
                {publicKey.toBase58().slice(0, 4)}...{publicKey.toBase58().slice(-4)}
              </span>
            </div>
          )}
          {mounted ? (
            <WalletMultiButton className="!h-9 !rounded-xl !border !border-[color:var(--olive-700)] !bg-[color:var(--olive-700)] !text-sm !font-semibold !text-white hover:!bg-[color:var(--olive-500)]" />
          ) : (
            <div className="h-9 w-36 rounded-xl border border-[color:var(--olive-700)] bg-[color:var(--olive-700)]" />
          )}
        </div>
      </div>
    </nav>
  );
}

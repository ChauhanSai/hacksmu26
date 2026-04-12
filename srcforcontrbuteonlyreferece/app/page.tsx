"use client";

import { useWallet } from "@solana/wallet-adapter-react";
import { LandingPage } from "@/components/landing-page";
import { Nav } from "@/components/nav";
import { MarketplaceHub } from "@/components/marketplace-hub";

export default function Home() {
  const { connected } = useWallet();

  if (!connected) {
    return <LandingPage />;
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
      <Nav />
      <main className="mx-auto max-w-6xl px-6 py-10">
        <MarketplaceHub />
      </main>
    </div>
  );
}

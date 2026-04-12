"use client";

import { useState } from "react";
import { useEffect } from "react";
import { useWalletModal } from "@solana/wallet-adapter-react-ui";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";

import { WinnerModal } from "./winner-modal";

interface Listing {
  id: string;
  title: string;
  description: string;
  imageUrl: string;
  ticketPriceSol: number;
  maxTickets: number;
  soldTickets: number;
  status: "open" | "closed";
  category: string;
}

const LISTINGS: Listing[] = [
  {
    id: "1",
    title: "CryptoPunk #3841",
    description: "Rare alien CryptoPunk with 3 attributes.",
    imageUrl: "https://substackcdn.com/image/fetch/$s_!l7dH!,f_auto,q_auto:good,fl_progressive:steep/https%3A%2F%2Fbucketeer-e05bbc84-baa3-437e-9518-adb32be77984.s3.amazonaws.com%2Fpublic%2Fimages%2F52c18f05-0251-463f-8128-8add0c4ee71c_600x600.png",
    ticketPriceSol: 0.5,
    maxTickets: 50,
    soldTickets: 32,
    status: "open",
    category: "Collectibles",
  },
  {
    id: "2",
    title: "Bored Ape #7304 — Gold Fur",
    description: "Rare trait combo in BAYC.",
    imageUrl: "https://backend.artreview.com/wp-content/uploads/2021/11/cryptopunks-1230x1230.jpg",
    ticketPriceSol: 0.1,
    maxTickets: 20,
    soldTickets: 14,
    status: "open",
    category: "Collectibles",
  },
  {
    id: "3",
    title: "Azuki #1199 — Red Bean",
    description: "Top rarity tier Azuki.",
    imageUrl: "https://dailycoin.com/wp-content/uploads/2024/04/Solana_NFTs_Gorilla_Ape_Question_Wireframe_Crypto_web.jpg",
    ticketPriceSol: 0.08,
    maxTickets: 200,
    soldTickets: 187,
    status: "open",
    category: "PFP",
  },
  {
    id: "4",
    title: "Fidenza #313",
    description: "Iconic generative artwork.",
    imageUrl: "https://static01.nyt.com/images/2021/03/11/arts/11nft-explain-1/merlin_184196631_939fb22d-b909-4205-99d9-b464fb961d32-articleLarge.jpg?quality=75&auto=webp&disable=upscale",
    ticketPriceSol: 0.5,
    maxTickets: 30,
    soldTickets: 11,
    status: "open",
    category: "Gen Art",
  },
  {
    id: "5",
    title: "Doodle #6914",
    description: "Rainbow doodle collectible.",
    imageUrl: "https://hips.hearstapps.com/hmg-prod/images/nft-1-1614978591.jpg?crop=0.5xw:1xh;center,top&resize=640:*",
    ticketPriceSol: 0.06,
    maxTickets: 75,
    soldTickets: 75,
    status: "closed",
    category: "Art",
  },
  {
    id: "6",
    title: "Pudgy Penguin #4028",
    description: "Top 5% rarity penguin.",
    imageUrl: "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTPNsXhWI5yCBUXDzuFM2QnLm3k25HuWiODjA&s",
    ticketPriceSol: 0.07,
    maxTickets: 150,
    soldTickets: 89,
    status: "open",
    category: "Collectibles",
  },
];

const CATEGORIES = ["All", "Collectibles", "PFP", "Gen Art", "Art"];

function ListingCard({ listing, onCardClick }: { listing: Listing; onCardClick: () => void }) {
  const ticketsLeft = Math.max(0, listing.maxTickets - listing.soldTickets);

  return (
    <button
      onClick={onCardClick}
      className="group block w-full overflow-hidden rounded-2xl border border-[color:var(--surface-border)] bg-white text-left shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md focus:outline-none"
    >
      <div className="relative h-56 w-full overflow-hidden">
        <img
          src={listing.imageUrl}
          alt={listing.title}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
        <div className="absolute left-3 top-3 rounded-full bg-white/90 px-2.5 py-1 text-xs font-semibold text-[color:var(--ink)]">
          {listing.category}
        </div>
        <div
          className={`absolute right-3 top-3 rounded-full px-2.5 py-1 text-xs font-semibold ${
            listing.status === "open"
              ? "bg-[color:var(--olive-100)] text-[color:var(--olive-700)]"
              : "bg-gray-200 text-gray-600"
          }`}
        >
          {listing.status === "open" ? "LIVE" : "CLOSED"}
        </div>
      </div>

      <div className="space-y-2 px-4 py-3">
        <p className="truncate text-base font-semibold text-[color:var(--ink)]">{listing.title}</p>
        <p className="line-clamp-1 text-sm text-[color:var(--ink-secondary)]">{listing.description}</p>

        <div className="flex items-center justify-between text-sm">
          <span className="text-[color:var(--ink-secondary)]">Price</span>
          <span className="font-semibold text-[color:var(--ink)]">{listing.ticketPriceSol.toFixed(2)} SOL</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-[color:var(--ink-secondary)]">Tickets left</span>
          <span className="font-semibold text-[color:var(--ink)]">{ticketsLeft}</span>
        </div>
      </div>
    </button>
  );
}

export function LandingPage() {
  const { setVisible } = useWalletModal();
  const [winnerListing, setWinnerListing] = useState<Listing | null>(null);
  const [activeCategory, setActiveCategory] = useState("All");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  function handleCardClick(listing: Listing) {
    if (listing.status === "closed") {
      setWinnerListing(listing);
      return;
    }
    setVisible(true);
  }

  const filtered = activeCategory === "All"
    ? LISTINGS
    : LISTINGS.filter((l) => l.category === activeCategory);

  return (
    <div className="min-h-screen bg-[color:var(--bg-primary)]">
      <header className="border-b border-[color:var(--surface-border)] bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4">
          <img src="/blinkbounties-logo.svg" alt="Blinkbounties" className="block h-9 w-auto sm:h-10" />
          {mounted ? (
            <WalletMultiButton className="!h-10 !rounded-xl !border !border-[color:var(--olive-700)] !bg-[color:var(--olive-700)] !px-4 !text-sm !font-semibold !text-white hover:!bg-[color:var(--olive-500)]" />
          ) : (
            <div className="h-10 w-36 rounded-xl border border-[color:var(--olive-700)] bg-[color:var(--olive-700)]" />
          )}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-10">
        <section className="mb-6 flex flex-wrap gap-2">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                activeCategory === cat
                  ? "bg-[color:var(--olive-700)] text-white"
                  : "border border-[color:var(--surface-border)] bg-white text-[color:var(--ink-secondary)] hover:bg-[color:var(--olive-50)]"
              }`}
            >
              {cat}
            </button>
          ))}
        </section>

        <section>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((listing) => (
              <ListingCard
                key={listing.id}
                listing={listing}
                onCardClick={() => handleCardClick(listing)}
              />
            ))}
          </div>
          {filtered.length === 0 ? (
            <p className="py-16 text-center text-sm text-[color:var(--ink-secondary)]">
              No listings in this category yet.
            </p>
          ) : null}
        </section>
      </main>

      {winnerListing ? (
        <WinnerModal
          nftTitle={winnerListing.title}
          nftImage={winnerListing.imageUrl}
          onClose={() => setWinnerListing(null)}
        />
      ) : null}
    </div>
  );
}

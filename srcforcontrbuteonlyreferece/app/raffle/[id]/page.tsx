import { PublicKey } from "@solana/web3.js";
import Link from "next/link";
import { notFound } from "next/navigation";

import { RaffleDetailClient } from "@/components/raffle-detail-client";
import { APP_URL, connection, fetchPositionsByRaffle, fetchRaffleByAddress } from "@/lib/solana";

interface Props {
  params: Promise<{ id: string }>;
}

const statusClassName: Record<string, string> = {
  open: "bg-[color:var(--olive-100)] text-[color:var(--olive-700)]",
  closed: "bg-zinc-200 text-zinc-700",
};

export default async function RafflePage({ params }: Props) {
  const { id } = await params;

  let raffleAddress: PublicKey;
  try {
    raffleAddress = new PublicKey(id);
  } catch {
    notFound();
  }

  const raffle = await fetchRaffleByAddress(raffleAddress);
  if (!raffle) {
    notFound();
  }

  const buyers = await fetchPositionsByRaffle(connection, raffleAddress);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-6 py-10">
      <section className="rounded-2xl border border-[color:var(--surface-border)] bg-white p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.2em] text-[color:var(--ink-secondary)]">Raffle Listing</p>
        <div className="mt-3 grid gap-4 md:grid-cols-[1fr_1.2fr]">
          <img
            src={raffle.imageUrl || "/next.svg"}
            alt={raffle.title}
            className="h-64 w-full rounded-xl object-cover"
          />
          <div>
            <h1 className="text-3xl font-bold text-[color:var(--ink)]">{raffle.title}</h1>
            <p className="mt-2 text-[color:var(--ink-secondary)]">{raffle.description}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              <span className={`rounded-full px-3 py-1 font-semibold ${statusClassName[raffle.status]}`}>
                {raffle.status.toUpperCase()}
              </span>
              <span className="rounded-full bg-[color:var(--olive-50)] px-3 py-1 text-[color:var(--ink-secondary)]">
                {raffle.ticketPriceSol.toFixed(4)} SOL / ticket
              </span>
              <span className="rounded-full bg-[color:var(--olive-50)] px-3 py-1 text-[color:var(--ink-secondary)]">
                Sold {raffle.soldTickets}/{raffle.maxTickets}
              </span>
              <span className="rounded-full bg-[color:var(--olive-50)] px-3 py-1 text-[color:var(--ink-secondary)]">Seller: {raffle.seller}</span>
            </div>

            <div className="mt-4 rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--ink)] p-4 text-xs text-white">
              <p className="font-semibold text-[color:var(--olive-100)]">Action Endpoint</p>
              <code className="mt-2 block overflow-x-auto">{`${APP_URL}/api/actions/raffle/${raffle.address}`}</code>
            </div>
          </div>
        </div>
      </section>

      <RaffleDetailClient raffle={raffle} buyers={buyers} />

      <Link href="/" className="text-sm font-semibold text-[color:var(--olive-700)] underline">
        Back to marketplace
      </Link>
    </main>
  );
}

"use client";

import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { LAMPORTS_PER_SOL, Transaction } from "@solana/web3.js";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  buildCreateRaffleInstruction,
  fetchAllRaffles,
  fetchPositionsByBuyer,
  fetchRafflesBySeller,
  getRafflePda,
  type BuyerPositionAccount,
  type RaffleAccount,
} from "@/lib/solana";

type RoleTab = "poster" | "worker";
type StatusFilter = "all" | "open" | "closed";
const LOAD_TIMEOUT_MS = 12000;

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs);
    }),
  ]);
}

function RaffleCard({ item }: { item: RaffleAccount }) {
  const progressPct = Math.min(100, (item.soldTickets / item.maxTickets) * 100);
  const sellerShort = item.seller.slice(0, 6);

  return (
    <Link
      href={`/raffle/${item.address}`}
      className="group block w-full overflow-hidden rounded-2xl border border-[color:var(--surface-border)] bg-white text-left shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="flex items-center justify-between border-b border-[color:var(--surface-border)] px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[color:var(--olive-200)]">
            <span className="text-xs font-bold text-[color:var(--olive-700)]">{sellerShort[0]}</span>
          </div>
          <div>
            <p className="text-xs leading-none text-[color:var(--ink-secondary)]">Listed by</p>
            <p className="font-mono text-xs font-semibold leading-tight text-[color:var(--ink)]">{sellerShort}...</p>
          </div>
        </div>
        {item.status === "open" ? (
          <span className="rounded-full bg-[color:var(--olive-100)] px-2.5 py-1 text-xs font-semibold text-[color:var(--olive-700)]">LIVE</span>
        ) : (
          <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-500">CLOSED</span>
        )}
      </div>

      {item.imageUrl ? (
        <div className="relative h-48 w-full overflow-hidden">
          <img
            src={item.imageUrl}
            alt={item.title}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
          {item.status === "closed" ? (
            <div className="absolute inset-0 flex items-center justify-center bg-black/35">
              <span className="rounded-md bg-black/60 px-3 py-1 text-xs font-bold uppercase tracking-wide text-white">Closed</span>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="flex h-48 items-center justify-center bg-[color:var(--olive-50)]">
          <p className="text-4xl font-black text-[color:var(--olive-200)]">#</p>
        </div>
      )}

      <div className="px-4 py-3">
        <p className="truncate text-sm font-bold text-[color:var(--ink)]">{item.title}</p>
        <p className="mt-0.5 line-clamp-1 text-xs text-[color:var(--ink-secondary)]">{item.description}</p>

        <div className="mb-1 mt-3">
          <div className="mb-1 flex items-center justify-between text-xs text-[color:var(--ink-secondary)]">
            <span>{item.soldTickets} sold</span>
            <span>{item.maxTickets} max</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[color:var(--olive-100)]">
            <div className="h-full rounded-full bg-[color:var(--olive-500)] transition-all" style={{ width: `${progressPct}%` }} />
          </div>
        </div>

        <div className="flex items-baseline gap-1">
          <span className="text-xs text-[color:var(--ink-secondary)]">Price:</span>
          <span className="text-sm font-bold text-[color:var(--ink)]">SOL {item.ticketPriceSol.toFixed(4)}</span>
          <span className="ml-auto text-xs text-[color:var(--ink-secondary)]">{item.maxTickets - item.soldTickets} left</span>
        </div>

        <div className="mt-3 rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] px-3 py-2 text-center text-xs font-semibold text-[color:var(--olive-700)]">
          Open raffle
        </div>
      </div>
    </Link>
  );
}

export function MarketplaceHub() {
  const { connection } = useConnection();
  const wallet = useWallet();

  const [role, setRole] = useState<RoleTab>("worker");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [query, setQuery] = useState("");
  const [balance, setBalance] = useState<number | null>(null);
  const [allRaffles, setAllRaffles] = useState<RaffleAccount[]>([]);
  const [posterRaffles, setPosterRaffles] = useState<RaffleAccount[]>([]);
  const [myTickets, setMyTickets] = useState<BuyerPositionAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [ticketPrice, setTicketPrice] = useState("0.01");
  const [maxTickets, setMaxTickets] = useState("100");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const marketPromise = withTimeout(fetchAllRaffles(connection), LOAD_TIMEOUT_MS, "Fetch raffles");
        const balancePromise = wallet.publicKey
          ? withTimeout(connection.getBalance(wallet.publicKey, "confirmed"), LOAD_TIMEOUT_MS, "Fetch balance")
          : Promise.resolve(null);
        const sellerPromise = wallet.publicKey
          ? withTimeout(fetchRafflesBySeller(connection, wallet.publicKey), LOAD_TIMEOUT_MS, "Fetch seller raffles")
          : Promise.resolve([] as RaffleAccount[]);
        const ticketsPromise = wallet.publicKey
          ? withTimeout(fetchPositionsByBuyer(connection, wallet.publicKey), LOAD_TIMEOUT_MS, "Fetch buyer positions")
          : Promise.resolve([] as BuyerPositionAccount[]);

        const [marketResult, balanceResult, sellerResult, ticketsResult] = await Promise.allSettled([
          marketPromise,
          balancePromise,
          sellerPromise,
          ticketsPromise,
        ]);

        const market = marketResult.status === "fulfilled" ? marketResult.value : [];
        const walletBalance = balanceResult.status === "fulfilled" ? balanceResult.value : null;
        const sellerItems = sellerResult.status === "fulfilled" ? sellerResult.value : [];
        const ticketItems = ticketsResult.status === "fulfilled" ? ticketsResult.value : [];

        if (!cancelled) {
          setAllRaffles(market);
          setPosterRaffles(sellerItems);
          setMyTickets(ticketItems);
          setBalance(walletBalance === null ? null : walletBalance / LAMPORTS_PER_SOL);

          if (
            marketResult.status === "rejected" ||
            balanceResult.status === "rejected" ||
            sellerResult.status === "rejected" ||
            ticketsResult.status === "rejected"
          ) {
            const reasons = [marketResult, balanceResult, sellerResult, ticketsResult]
              .filter((r): r is PromiseRejectedResult => r.status === "rejected")
              .map((r) => (r.reason instanceof Error ? r.reason.message : String(r.reason)));
            setError(reasons[0] ?? "Some wallet/market data could not be loaded.");
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          const message = loadError instanceof Error ? loadError.message : "Failed to load marketplace.";
          if (message.toLowerCase().includes("429") || message.toLowerCase().includes("too many requests")) {
            setError("RPC is rate-limited right now. Wait 10-20 seconds and click Refresh.");
          } else {
            setError(message);
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => { cancelled = true; };
  }, [connection, wallet.publicKey, reloadToken]);

  const filtered = useMemo(() => {
    return allRaffles.filter((item) => {
      const statusOk = statusFilter === "all" || item.status === statusFilter;
      const queryOk =
        !query.trim() ||
        item.title.toLowerCase().includes(query.toLowerCase()) ||
        item.description.toLowerCase().includes(query.toLowerCase());
      return statusOk && queryOk;
    });
  }, [allRaffles, query, statusFilter]);

  async function createListing() {
    if (!wallet.publicKey || !wallet.sendTransaction) {
      setCreateError("Connect wallet first.");
      return;
    }

    setCreateError(null);
    setCreating(true);

    try {
      const priceSol = Number(ticketPrice);
      const max = Number(maxTickets);
      if (!title.trim() || !description.trim()) throw new Error("Title and description are required.");
      if (!Number.isFinite(priceSol) || priceSol <= 0) throw new Error("Invalid ticket price.");
      if (!Number.isFinite(max) || max <= 0) throw new Error("Invalid max tickets.");
      if (!/^https?:\/\//i.test(imageUrl.trim())) {
        throw new Error("Image URL must be a public http(s) link. Do not paste base64 data URLs.");
      }
      if (imageUrl.trim().length > 300) {
        throw new Error("Image URL is too long. Use a shorter hosted image link.");
      }

      const raffleId = BigInt(Date.now());
      const rafflePda = getRafflePda(wallet.publicKey, raffleId);
      const priceLamports = BigInt(Math.round(priceSol * LAMPORTS_PER_SOL));

      const tx = new Transaction();
      const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash("confirmed");
      tx.feePayer = wallet.publicKey;
      tx.recentBlockhash = blockhash;
      tx.add(
        buildCreateRaffleInstruction({
          seller: wallet.publicKey,
          raffle: rafflePda,
          raffleId,
          ticketPriceLamports: priceLamports,
          maxTickets: max,
          title: title.trim(),
          description: description.trim(),
          imageUrl: imageUrl.trim(),
        }),
      );

      const simulation = await connection.simulateTransaction(tx);
      if (simulation.value.err) {
        const simulationDetails = simulation.value.logs?.slice(-6).join(" | ");
        throw new Error(
          `Preflight failed: ${JSON.stringify(simulation.value.err)}${simulationDetails ? ` (${simulationDetails})` : ""}`,
        );
      }

      const signature = await wallet.sendTransaction(tx, connection, {
        preflightCommitment: "confirmed",
      });
      await connection.confirmTransaction({ signature, blockhash, lastValidBlockHeight }, "confirmed");

      setTitle("");
      setDescription("");
      setImageUrl("");
      setReloadToken((curr) => curr + 1);
    } catch (createListingError) {
      setCreateError(
        createListingError instanceof Error ? createListingError.message : "Failed to create listing.",
      );
    } finally {
      setCreating(false);
    }
  }

  const walletShort = wallet.publicKey
    ? `${wallet.publicKey.toBase58().slice(0, 4)}...${wallet.publicKey.toBase58().slice(-4)}`
    : "Not connected";

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-[color:var(--surface-border)] bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-widest text-[color:var(--olive-700)]">Raffle Market</p>
            <h2 className="mt-1 text-2xl font-bold text-[color:var(--ink)]">Browse and manage listings</h2>
          </div>

          <div className="min-w-[210px] rounded-2xl border border-[color:var(--olive-200)] bg-white px-4 py-3 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-[color:var(--ink-secondary)]">Current Balance</p>
              <span className="h-2.5 w-2.5 rounded-full bg-[color:var(--olive-500)]" />
            </div>
            <p className="mt-1 text-2xl font-bold leading-none text-[color:var(--olive-700)]">
              {balance === null ? "--" : `${balance.toFixed(4)} SOL`}
            </p>
            <p className="mt-2 truncate font-mono text-xs text-[color:var(--ink-secondary)]">{walletShort}</p>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2.5">
          <span className="text-sm font-medium text-[color:var(--ink-secondary)]">Role:</span>
          <div className="flex rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] p-1">
            <button
              type="button"
              onClick={() => setRole("worker")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
                role === "worker" ? "bg-white text-[color:var(--ink)] shadow-sm" : "text-[color:var(--ink-secondary)]"
              }`}
            >
              Buyer
            </button>
            <button
              type="button"
              onClick={() => setRole("poster")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
                role === "poster" ? "bg-white text-[color:var(--ink)] shadow-sm" : "text-[color:var(--ink-secondary)]"
              }`}
            >
              Seller
            </button>
          </div>
          <button
            type="button"
            onClick={() => setReloadToken((curr) => curr + 1)}
            className="rounded-xl border border-[color:var(--olive-200)] bg-[color:var(--olive-100)] px-3 py-2 text-sm font-semibold text-[color:var(--olive-700)] transition-colors hover:bg-[color:var(--olive-200)]"
          >
            Refresh
          </button>
        </div>
      </section>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-[color:var(--ink-secondary)]">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-[color:var(--olive-500)] border-t-transparent" />
          Loading marketplace...
        </div>
      ) : null}
      {error ? <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-600">{error}</p> : null}

      {role === "poster" ? (
        <>
          <section className="rounded-2xl border border-[color:var(--surface-border)] bg-white p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-[color:var(--ink)]">Create New Listing</h3>
            <p className="mt-1 text-sm text-[color:var(--ink-secondary)]">List your item and start ticket sales on-chain.</p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Item title"
                className="h-11 rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] px-3 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--ink-secondary)] focus:border-[color:var(--olive-500)] focus:bg-white focus:outline-none transition-colors" />
              <input value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder="Image URL (https://...)"
                className="h-11 rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] px-3 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--ink-secondary)] focus:border-[color:var(--olive-500)] focus:bg-white focus:outline-none transition-colors" />
              <input value={ticketPrice} onChange={(e) => setTicketPrice(e.target.value)} placeholder="Ticket price (SOL)"
                className="h-11 rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] px-3 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--ink-secondary)] focus:border-[color:var(--olive-500)] focus:bg-white focus:outline-none transition-colors" />
              <input value={maxTickets} onChange={(e) => setMaxTickets(e.target.value)} placeholder="Max tickets"
                className="h-11 rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] px-3 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--ink-secondary)] focus:border-[color:var(--olive-500)] focus:bg-white focus:outline-none transition-colors" />
            </div>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe the item and raffle rules"
              className="mt-3 min-h-24 w-full rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] px-3 py-2 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--ink-secondary)] focus:border-[color:var(--olive-500)] focus:bg-white focus:outline-none transition-colors" />
            <button onClick={createListing} disabled={creating}
              className="mt-3 rounded-xl bg-[color:var(--olive-700)] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[color:var(--olive-500)] disabled:opacity-50">
              {creating ? "Creating..." : "Create Raffle"}
            </button>
            {createError ? <p className="mt-2 text-sm text-red-600">{createError}</p> : null}
          </section>

          <section className="rounded-2xl border border-[color:var(--surface-border)] bg-white p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-[color:var(--ink)]">Your Listings</h3>
            <p className="mt-1 text-sm text-[color:var(--ink-secondary)]">Open a listing card to review buyers and manage payout.</p>
            {posterRaffles.length > 0 ? (
              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {posterRaffles.map((item) => (
                  <RaffleCard key={item.address} item={item} />
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-[color:var(--ink-secondary)]">No listings yet.</p>
            )}
          </section>
        </>
      ) : (
        <>
          <section className="rounded-2xl border border-[color:var(--surface-border)] bg-white p-5 shadow-sm">
            <div className="flex flex-wrap gap-3">
              <input
                placeholder="Search listings..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="h-10 min-w-52 flex-1 rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] px-3 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--ink-secondary)] focus:border-[color:var(--olive-500)] focus:bg-white focus:outline-none transition-colors"
              />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
                className="h-10 rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] px-3 text-sm text-[color:var(--ink)] focus:border-[color:var(--olive-500)] focus:outline-none transition-colors"
              >
                <option value="all">All statuses</option>
                <option value="open">Open</option>
                <option value="closed">Closed</option>
              </select>
            </div>

            {filtered.length > 0 ? (
              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {filtered.map((item) => (
                  <RaffleCard key={item.address} item={item} />
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-[color:var(--ink-secondary)]">No listings matched your filter.</p>
            )}
          </section>

          <section className="rounded-2xl border border-[color:var(--surface-border)] bg-white p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-[color:var(--ink)]">My Tickets</h3>
            <p className="mt-1 text-sm text-[color:var(--ink-secondary)]">Raffles where your wallet holds tickets.</p>
            {myTickets.length > 0 ? (
              <div className="mt-3 space-y-2">
                {myTickets.map((position) => (
                  <div key={position.address} className="flex items-center justify-between rounded-xl border border-[color:var(--surface-border)] bg-[color:var(--olive-50)] p-3 text-sm">
                    <div>
                      <p className="max-w-48 truncate font-mono text-xs font-semibold text-[color:var(--ink)]">{position.raffle}</p>
                      <p className="text-[color:var(--ink-secondary)]">{position.tickets} ticket{position.tickets !== 1 ? "s" : ""} · {position.spentSol.toFixed(4)} SOL spent</p>
                    </div>
                    <Link href={`/raffle/${position.raffle}`} className="shrink-0 rounded-lg border border-[color:var(--olive-200)] bg-white px-3 py-1.5 text-xs font-semibold text-[color:var(--olive-700)] transition-colors hover:bg-[color:var(--olive-100)]">
                      View
                    </Link>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-[color:var(--ink-secondary)]">No tickets purchased yet.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}

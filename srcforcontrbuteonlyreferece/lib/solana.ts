import { BN, BorshCoder, type Idl } from "@coral-xyz/anchor";
import {
  clusterApiUrl,
  Connection,
  LAMPORTS_PER_SOL,
  PublicKey,
  SystemProgram,
  Transaction,
  TransactionInstruction,
} from "@solana/web3.js";
import { z } from "zod";

import { BLINK_BOUNTIES_IDL } from "@/lib/idl/blink_bounties";

const DEFAULT_PROGRAM_ID = "3MAR3HqMntaDfPE1Vmf1XGBeCEv2dykXUCjwsMB8gF1S";

const envSchema = z.object({
  NEXT_PUBLIC_SOLANA_RPC_URL: z.string().url().optional(),
  NEXT_PUBLIC_PROGRAM_ID: z.string().optional(),
  NEXT_PUBLIC_APP_URL: z.string().url().optional(),
});

const env = envSchema.parse({
  NEXT_PUBLIC_SOLANA_RPC_URL: process.env.NEXT_PUBLIC_SOLANA_RPC_URL,
  NEXT_PUBLIC_PROGRAM_ID: process.env.NEXT_PUBLIC_PROGRAM_ID,
  NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
});

export const SOLANA_RPC_URL = env.NEXT_PUBLIC_SOLANA_RPC_URL ?? clusterApiUrl("devnet");
export const PROGRAM_ID = new PublicKey(env.NEXT_PUBLIC_PROGRAM_ID ?? DEFAULT_PROGRAM_ID);
export const APP_URL = env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";

export const connection = new Connection(SOLANA_RPC_URL, "confirmed");

const coder = new BorshCoder(BLINK_BOUNTIES_IDL as Idl);

export type RaffleStatus = "open" | "closed";

interface DecodedRaffle {
  seller: PublicKey;
  raffle_id: BN;
  ticket_price: BN;
  max_tickets: number;
  sold_tickets: number;
  title: string;
  description: string;
  image_url: string;
  status: Record<string, unknown>;
  bump: number;
}

interface DecodedBuyerPosition {
  raffle: PublicKey;
  buyer: PublicKey;
  tickets: number;
  spent: BN;
  bump: number;
}

const RAFFLE_DISCRIMINATOR = Buffer.from([143, 133, 63, 173, 138, 10, 142, 200]);
const BUYER_POSITION_DISCRIMINATOR = Buffer.from([232, 163, 167, 95, 170, 210, 214, 83]);

function isRateLimitError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const message = error.message.toLowerCase();
  return message.includes("429") || message.includes("too many requests") || message.includes("rate limit");
}

async function withRpcRetry<T>(fn: () => Promise<T>, maxRetries = 2): Promise<T> {
  let attempt = 0;
  while (true) {
    try {
      return await fn();
    } catch (error) {
      if (!isRateLimitError(error) || attempt >= maxRetries) {
        throw error;
      }
      const delayMs = 400 * (attempt + 1);
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      attempt += 1;
    }
  }
}

export interface RaffleAccount {
  address: string;
  seller: string;
  raffleId: string;
  ticketPriceLamports: string;
  ticketPriceSol: number;
  maxTickets: number;
  soldTickets: number;
  title: string;
  description: string;
  imageUrl: string;
  status: RaffleStatus;
  bump: number;
}

export interface BuyerPositionAccount {
  address: string;
  raffle: string;
  buyer: string;
  tickets: number;
  spentLamports: string;
  spentSol: number;
  bump: number;
}

function normalizeStatus(status: Record<string, unknown>): RaffleStatus {
  const raw = Object.keys(status)[0]?.toLowerCase();
  return raw === "closed" ? "closed" : "open";
}

function parseRaffle(address: PublicKey, data: Buffer): RaffleAccount {
  const decoded = coder.accounts.decode("Raffle", data) as DecodedRaffle;
  const ticketPriceLamports = decoded.ticket_price.toString();
  return {
    address: address.toBase58(),
    seller: decoded.seller.toBase58(),
    raffleId: decoded.raffle_id.toString(),
    ticketPriceLamports,
    ticketPriceSol: Number(ticketPriceLamports) / LAMPORTS_PER_SOL,
    maxTickets: decoded.max_tickets,
    soldTickets: decoded.sold_tickets,
    title: decoded.title,
    description: decoded.description,
    imageUrl: decoded.image_url,
    status: normalizeStatus(decoded.status),
    bump: decoded.bump,
  };
}

function parseBuyerPosition(address: PublicKey, data: Buffer): BuyerPositionAccount {
  const decoded = coder.accounts.decode("BuyerPosition", data) as DecodedBuyerPosition;
  const spentLamports = decoded.spent.toString();
  return {
    address: address.toBase58(),
    raffle: decoded.raffle.toBase58(),
    buyer: decoded.buyer.toBase58(),
    tickets: decoded.tickets,
    spentLamports,
    spentSol: Number(spentLamports) / LAMPORTS_PER_SOL,
    bump: decoded.bump,
  };
}

function hasDiscriminator(data: Buffer, discriminator: Buffer): boolean {
  if (data.length < 8) return false;
  return data.subarray(0, 8).equals(discriminator);
}

export function getRafflePda(seller: PublicKey, raffleId: bigint): PublicKey {
  const raffleIdBuffer = new BN(raffleId.toString()).toArrayLike(Buffer, "le", 8);
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("raffle"), seller.toBuffer(), raffleIdBuffer],
    PROGRAM_ID,
  );
  return pda;
}

export function getBuyerPositionPda(raffle: PublicKey, buyer: PublicKey): PublicKey {
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("position"), raffle.toBuffer(), buyer.toBuffer()],
    PROGRAM_ID,
  );
  return pda;
}

export async function fetchRaffleByAddress(address: PublicKey): Promise<RaffleAccount | null> {
  const info = await withRpcRetry(() => connection.getAccountInfo(address));
  if (!info) return null;
  return parseRaffle(address, info.data);
}

export async function fetchAllRaffles(rpcConnection: Connection): Promise<RaffleAccount[]> {
  const accounts = await withRpcRetry(() =>
    rpcConnection.getProgramAccounts(PROGRAM_ID, {
      filters: [{ memcmp: { offset: 0, bytes: "R1L4cMRuGB9" } }],
    }),
  );
  const list = accounts
    .filter((account) => hasDiscriminator(account.account.data, RAFFLE_DISCRIMINATOR))
    .flatMap((account) => {
      try {
        return [parseRaffle(account.pubkey, account.account.data)];
      } catch {
        return [];
      }
    });
  return list.sort((a, b) => Number(b.raffleId) - Number(a.raffleId));
}

export async function fetchRafflesBySeller(
  rpcConnection: Connection,
  seller: PublicKey,
): Promise<RaffleAccount[]> {
  const accounts = await withRpcRetry(() =>
    rpcConnection.getProgramAccounts(PROGRAM_ID, {
      filters: [
        { memcmp: { offset: 0, bytes: "R1L4cMRuGB9" } },
        { memcmp: { offset: 8, bytes: seller.toBase58() } },
      ],
    }),
  );
  const list = accounts
    .filter((account) => hasDiscriminator(account.account.data, RAFFLE_DISCRIMINATOR))
    .flatMap((account) => {
      try {
        return [parseRaffle(account.pubkey, account.account.data)];
      } catch {
        return [];
      }
    });
  return list.sort((a, b) => Number(b.raffleId) - Number(a.raffleId));
}

export async function fetchPositionsByBuyer(
  rpcConnection: Connection,
  buyer: PublicKey,
): Promise<BuyerPositionAccount[]> {
  const accounts = await withRpcRetry(() =>
    rpcConnection.getProgramAccounts(PROGRAM_ID, {
      filters: [
        { memcmp: { offset: 0, bytes: "futkuHCnA98" } },
        { memcmp: { offset: 8 + 32, bytes: buyer.toBase58() } },
      ],
    }),
  );
  return accounts
    .filter((account) => hasDiscriminator(account.account.data, BUYER_POSITION_DISCRIMINATOR))
    .flatMap((account) => {
      try {
        return [parseBuyerPosition(account.pubkey, account.account.data)];
      } catch {
        return [];
      }
    });
}

export async function fetchPositionsByRaffle(
  rpcConnection: Connection,
  raffle: PublicKey,
): Promise<BuyerPositionAccount[]> {
  const accounts = await withRpcRetry(() =>
    rpcConnection.getProgramAccounts(PROGRAM_ID, {
      filters: [
        { memcmp: { offset: 0, bytes: "futkuHCnA98" } },
        { memcmp: { offset: 8, bytes: raffle.toBase58() } },
      ],
    }),
  );
  return accounts
    .filter((account) => hasDiscriminator(account.account.data, BUYER_POSITION_DISCRIMINATOR))
    .flatMap((account) => {
      try {
        return [parseBuyerPosition(account.pubkey, account.account.data)];
      } catch {
        return [];
      }
    });
}

export function buildCreateRaffleInstruction(args: {
  seller: PublicKey;
  raffle: PublicKey;
  raffleId: bigint;
  ticketPriceLamports: bigint;
  maxTickets: number;
  title: string;
  description: string;
  imageUrl: string;
}): TransactionInstruction {
  const data = coder.instruction.encode("create_raffle", {
    raffle_id: new BN(args.raffleId.toString()),
    ticket_price: new BN(args.ticketPriceLamports.toString()),
    max_tickets: args.maxTickets,
    title: args.title,
    description: args.description,
    image_url: args.imageUrl,
  });

  return new TransactionInstruction({
    programId: PROGRAM_ID,
    keys: [
      { pubkey: args.seller, isSigner: true, isWritable: true },
      { pubkey: args.raffle, isSigner: false, isWritable: true },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
    ],
    data,
  });
}

export function buildBuyTicketsInstruction(args: {
  buyer: PublicKey;
  raffle: PublicKey;
  buyerPosition: PublicKey;
  quantity: number;
}): TransactionInstruction {
  const data = coder.instruction.encode("buy_tickets", {
    quantity: args.quantity,
  });

  return new TransactionInstruction({
    programId: PROGRAM_ID,
    keys: [
      { pubkey: args.buyer, isSigner: true, isWritable: true },
      { pubkey: args.raffle, isSigner: false, isWritable: true },
      { pubkey: args.buyerPosition, isSigner: false, isWritable: true },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
    ],
    data,
  });
}

export function buildCloseRaffleInstruction(args: {
  seller: PublicKey;
  raffle: PublicKey;
}): TransactionInstruction {
  const data = coder.instruction.encode("close_raffle", {});
  return new TransactionInstruction({
    programId: PROGRAM_ID,
    keys: [
      { pubkey: args.seller, isSigner: true, isWritable: true },
      { pubkey: args.raffle, isSigner: false, isWritable: true },
    ],
    data,
  });
}

export function buildClaimProceedsInstruction(args: {
  seller: PublicKey;
  raffle: PublicKey;
}): TransactionInstruction {
  const data = coder.instruction.encode("claim_proceeds", {});
  return new TransactionInstruction({
    programId: PROGRAM_ID,
    keys: [
      { pubkey: args.seller, isSigner: true, isWritable: true },
      { pubkey: args.raffle, isSigner: false, isWritable: true },
    ],
    data,
  });
}

export async function buildBuyTicketsTransaction(args: {
  buyer: PublicKey;
  raffle: PublicKey;
  quantity: number;
}) {
  const buyerPosition = getBuyerPositionPda(args.raffle, args.buyer);
  const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash("confirmed");

  const tx = new Transaction({
    feePayer: args.buyer,
    blockhash,
    lastValidBlockHeight,
  });

  tx.add(
    buildBuyTicketsInstruction({
      buyer: args.buyer,
      raffle: args.raffle,
      buyerPosition,
      quantity: args.quantity,
    }),
  );

  return tx;
}

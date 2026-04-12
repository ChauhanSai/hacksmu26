import {
  ACTIONS_CORS_HEADERS,
  createActionHeaders,
  createPostResponse,
  type ActionGetResponse,
  type ActionPostRequest,
} from "@solana/actions";
import { PublicKey } from "@solana/web3.js";

import {
  APP_URL,
  buildBuyTicketsTransaction,
  fetchRaffleByAddress,
} from "@/lib/solana";

export const dynamic = "force-dynamic";

interface RouteParams {
  params: Promise<{ id: string }>;
}

function jsonError(message: string, status = 400) {
  return Response.json(
    { message },
    {
      status,
      headers: createActionHeaders({
        headers: ACTIONS_CORS_HEADERS,
        chainId: "devnet",
        actionVersion: "2.1",
      }),
    },
  );
}

export async function GET(_req: Request, { params }: RouteParams) {
  const { id } = await params;

  let rafflePubkey: PublicKey;
  try {
    rafflePubkey = new PublicKey(id);
  } catch {
    return jsonError("Invalid raffle id.", 404);
  }

  const raffle = await fetchRaffleByAddress(rafflePubkey);
  if (!raffle) {
    return jsonError("Raffle not found.", 404);
  }

  const payload: ActionGetResponse = {
    type: "action",
    icon: raffle.imageUrl || `${APP_URL}/next.svg`,
    title: `${raffle.title} · ${raffle.ticketPriceSol.toFixed(4)} SOL/ticket`,
    description: raffle.description,
    label: "Buy Tickets",
    disabled: raffle.status !== "open",
    links: {
      actions: [
        {
          type: "transaction",
          href: `${APP_URL}/api/actions/raffle/${id}?quantity=1`,
          label: "Buy 1 Ticket",
        },
        {
          type: "transaction",
          href: `${APP_URL}/api/actions/raffle/${id}?quantity=2`,
          label: "Buy 2 Tickets",
        },
        {
          type: "transaction",
          href: `${APP_URL}/api/actions/raffle/${id}?quantity=3`,
          label: "Buy 3 Tickets",
        },
      ],
    },
  };

  return Response.json(payload, {
    headers: createActionHeaders({
      headers: ACTIONS_CORS_HEADERS,
      chainId: "devnet",
      actionVersion: "2.1",
    }),
  });
}

export async function POST(req: Request, { params }: RouteParams) {
  const { id } = await params;

  let rafflePubkey: PublicKey;
  try {
    rafflePubkey = new PublicKey(id);
  } catch {
    return jsonError("Invalid raffle id.", 404);
  }

  const raffle = await fetchRaffleByAddress(rafflePubkey);
  if (!raffle) {
    return jsonError("Raffle not found.", 404);
  }

  if (raffle.status !== "open") {
    return jsonError("Raffle is closed.", 409);
  }

  const url = new URL(req.url);
  const queryQty = Number(url.searchParams.get("quantity") ?? "1");

  let body: ActionPostRequest;
  try {
    body = (await req.json()) as ActionPostRequest;
  } catch {
    return jsonError("Invalid POST body.");
  }

  let buyer: PublicKey;
  try {
    buyer = new PublicKey(body.account);
  } catch {
    return jsonError("Invalid wallet account.");
  }

  const data = body.data as Record<string, string | string[]> | undefined;
  const bodyQtyCandidate = typeof data?.quantity === "string" ? Number(data.quantity) : NaN;
  const quantity = Number.isFinite(bodyQtyCandidate) ? bodyQtyCandidate : queryQty;
  if (![1, 2, 3].includes(quantity)) {
    return jsonError("Quantity must be 1, 2, or 3.");
  }

  const tx = await buildBuyTicketsTransaction({
    buyer,
    raffle: rafflePubkey,
    quantity,
  });

  const payload = await createPostResponse({
    fields: {
      type: "transaction",
      transaction: tx,
      message: `Buy ${quantity} raffle ticket(s)`,
    },
  });

  return Response.json(payload, {
    headers: createActionHeaders({
      headers: ACTIONS_CORS_HEADERS,
      chainId: "devnet",
      actionVersion: "2.1",
    }),
  });
}

export async function OPTIONS() {
  return new Response(null, {
    headers: createActionHeaders({
      headers: ACTIONS_CORS_HEADERS,
      chainId: "devnet",
      actionVersion: "2.1",
    }),
  });
}

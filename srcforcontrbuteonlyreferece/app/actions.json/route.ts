import {
  createActionHeaders,
  type ActionsJson,
} from "@solana/actions";

export const dynamic = "force-dynamic";

export async function GET() {
  const payload: ActionsJson = {
    rules: [
      {
        pathPattern: "/raffle/*",
        apiPath: "/api/actions/raffle/*",
      },
    ],
  };

  return Response.json(payload, {
    headers: createActionHeaders({
      chainId: "devnet",
      actionVersion: "2.1",
    }),
  });
}

export async function OPTIONS() {
  return new Response(null, {
    headers: createActionHeaders({
      chainId: "devnet",
      actionVersion: "2.1",
    }),
  });
}

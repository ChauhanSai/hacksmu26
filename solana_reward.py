"""Send SOL from a treasury wallet to a contributor (devnet demo)."""

from __future__ import annotations

import os
import uuid
from typing import Tuple

try:
    import base58
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.system_program import TransferParams, transfer
    from solders.transaction import Transaction
    from solana.rpc.api import Client
    from solana.rpc.types import TxOpts
except ImportError:
    base58 = None  # type: ignore


def send_sol_reward(
    to_wallet: str,
    lamports: int,
    *,
    rpc_url: str | None = None,
    treasury_secret_b58: str | None = None,
) -> Tuple[str | None, str | None]:
    """
    Transfer lamports from treasury to `to_wallet`.
    Returns (signature, error_message). If no treasury key is set, returns a MOCK signature.
    """
    rpc = rpc_url or os.environ.get("SOLANA_RPC_URL", "https://api.devnet.solana.com")
    sk = treasury_secret_b58 or os.environ.get("TREASURY_SECRET_KEY", "").strip()

    if not sk:
        return f"MOCK:{uuid.uuid4().hex}", None

    if base58 is None:
        return None, "solana / solders packages not installed (pip install solana base58)"

    try:
        raw = base58.b58decode(sk)
        treasury = Keypair.from_bytes(raw)
    except Exception as exc:
        return None, f"Invalid TREASURY_SECRET_KEY: {exc}"

    try:
        to_pubkey = Pubkey.from_string(to_wallet.strip())
    except Exception as exc:
        return None, f"Invalid recipient wallet: {exc}"

    try:
        client = Client(rpc)
        ix = transfer(
            TransferParams(
                from_pubkey=treasury.pubkey(),
                to_pubkey=to_pubkey,
                lamports=int(lamports),
            )
        )
        bh = client.get_latest_blockhash().value.blockhash
        tx = Transaction.new_signed_with_payer([ix], treasury.pubkey(), [treasury], bh)
        resp = client.send_transaction(tx, opts=TxOpts(skip_preflight=False, preflight_commitment="confirmed"))
        sig = resp.value
        if sig is None:
            return None, "RPC returned no signature"
        return str(sig), None
    except Exception as exc:
        return None, str(exc)

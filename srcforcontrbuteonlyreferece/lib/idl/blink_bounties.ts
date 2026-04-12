import type { Idl } from "@coral-xyz/anchor";

export const BLINK_BOUNTIES_IDL = {
  address: "3MAR3HqMntaDfPE1Vmf1XGBeCEv2dykXUCjwsMB8gF1S",
  metadata: {
    name: "blink_bounties",
    version: "0.2.0",
    spec: "0.1.0",
    description: "Raffle marketplace powered by Solana blinks",
  },
  instructions: [
    {
      name: "create_raffle",
      discriminator: [226, 206, 159, 34, 213, 207, 98, 126],
      accounts: [
        { name: "seller", writable: true, signer: true },
        { name: "raffle", writable: true },
        { name: "system_program", address: "11111111111111111111111111111111" },
      ],
      args: [
        { name: "raffle_id", type: "u64" },
        { name: "ticket_price", type: "u64" },
        { name: "max_tickets", type: "u32" },
        { name: "title", type: "string" },
        { name: "description", type: "string" },
        { name: "image_url", type: "string" },
      ],
    },
    {
      name: "buy_tickets",
      discriminator: [48, 16, 122, 137, 24, 214, 198, 58],
      accounts: [
        { name: "buyer", writable: true, signer: true },
        { name: "raffle", writable: true },
        { name: "buyer_position", writable: true },
        { name: "system_program", address: "11111111111111111111111111111111" },
      ],
      args: [{ name: "quantity", type: "u8" }],
    },
    {
      name: "close_raffle",
      discriminator: [220, 129, 128, 51, 70, 66, 209, 124],
      accounts: [
        { name: "seller", writable: true, signer: true },
        { name: "raffle", writable: true },
      ],
      args: [],
    },
    {
      name: "claim_proceeds",
      discriminator: [44, 76, 121, 111, 124, 251, 237, 5],
      accounts: [
        { name: "seller", writable: true, signer: true },
        { name: "raffle", writable: true },
      ],
      args: [],
    },
  ],
  accounts: [
    {
      name: "Raffle",
      discriminator: [143, 133, 63, 173, 138, 10, 142, 200],
    },
    {
      name: "BuyerPosition",
      discriminator: [232, 163, 167, 95, 170, 210, 214, 83],
    },
  ],
  types: [
    {
      name: "Raffle",
      type: {
        kind: "struct",
        fields: [
          { name: "seller", type: "pubkey" },
          { name: "raffle_id", type: "u64" },
          { name: "ticket_price", type: "u64" },
          { name: "max_tickets", type: "u32" },
          { name: "sold_tickets", type: "u32" },
          { name: "title", type: "string" },
          { name: "description", type: "string" },
          { name: "image_url", type: "string" },
          { name: "status", type: { defined: { name: "RaffleStatus" } } },
          { name: "bump", type: "u8" },
        ],
      },
    },
    {
      name: "BuyerPosition",
      type: {
        kind: "struct",
        fields: [
          { name: "raffle", type: "pubkey" },
          { name: "buyer", type: "pubkey" },
          { name: "tickets", type: "u32" },
          { name: "spent", type: "u64" },
          { name: "bump", type: "u8" },
        ],
      },
    },
    {
      name: "RaffleStatus",
      type: {
        kind: "enum",
        variants: [{ name: "Open" }, { name: "Closed" }],
      },
    },
  ],
  errors: [
    { code: 6000, name: "InvalidAmount", msg: "Only positive amounts are allowed" },
    { code: 6001, name: "InvalidTicketQuantity", msg: "Invalid ticket quantity" },
    { code: 6002, name: "TitleTooLong", msg: "Raffle title exceeds max length" },
    { code: 6003, name: "DescriptionTooLong", msg: "Raffle description exceeds max length" },
    { code: 6004, name: "ImageUrlTooLong", msg: "Image URL exceeds max length" },
    { code: 6005, name: "RaffleClosed", msg: "Raffle is closed" },
    { code: 6006, name: "SoldOut", msg: "No tickets left" },
    { code: 6007, name: "Unauthorized", msg: "Unauthorized signer or account" },
    { code: 6008, name: "NothingToClaim", msg: "Nothing to claim" },
    { code: 6009, name: "MathOverflow", msg: "Math overflow" },
  ],
} satisfies Idl;

"use client";

const MOCK_WINNERS = [
  "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsE",
  "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
  "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
  "GU7ns9xCwgNPiAdJ69iusFkiS5CbMrkRuCBTBPMBoNvG",
  "HT8jvCx3NsRqPmW6DkL9fEaYuZbQoViXcMpGnTwKs4y",
  "3fZwQmVk8rDpN2sA6HcXuJtYLbEoWgMiCxFvTnPqKsR",
];

interface WinnerModalProps {
  nftTitle: string;
  nftImage?: string;
  onClose: () => void;
}

export function WinnerModal({ nftTitle, nftImage, onClose }: WinnerModalProps) {
  const winner = MOCK_WINNERS[Math.floor(Math.random() * MOCK_WINNERS.length)];
  const short = `${winner.slice(0, 6)}...${winner.slice(-6)}`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative w-full max-w-sm rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-2xl">
        {/* Top banner */}
        <div className="bg-gradient-to-r from-[color:var(--olive-700)] to-[color:var(--olive-500)] px-6 py-4 text-center">
          <p className="text-2xl">🏆</p>
          <h2 className="mt-1 text-lg font-bold text-white">Winner Announced!</h2>
        </div>

        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-white/70 transition-colors hover:text-white"
        >
          <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>

        <div className="p-6">
          {nftImage && (
            <div className="mb-4 overflow-hidden rounded-xl border border-gray-200">
              <img src={nftImage} alt={nftTitle} className="h-40 w-full object-cover" />
            </div>
          )}

          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-gray-400">NFT Transferred</p>
          <p className="text-base font-bold text-gray-900">{nftTitle}</p>

          <div className="mt-4 rounded-xl border border-green-200 bg-green-50 p-4">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-[color:var(--olive-700)]">New Owner</p>
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 shrink-0 rounded-full bg-gradient-to-br from-[color:var(--olive-700)] to-[color:var(--olive-400)]" />
              <p className="font-mono text-sm font-semibold text-gray-900">{short}</p>
            </div>
            <p className="mt-2 text-xs text-gray-500">
              This NFT has been transferred to the winner&apos;s wallet on Solana.
            </p>
          </div>

          <button
            onClick={onClose}
            className="mt-4 w-full rounded-xl bg-[color:var(--olive-700)] py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[color:var(--olive-500)]"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

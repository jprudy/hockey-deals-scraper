"use client";

import Link from "next/link";
import { useState } from "react";
import type { Deal } from "@/lib/deals/types";
import { formatPriceCents } from "@/lib/money";

function isValidPriceCents(value: number | undefined): value is number {
  return Number.isFinite(value) && value > 0;
}

export default function DealCard({ deal }: { deal: Deal }) {
  const [imageFailed, setImageFailed] = useState(false);
  const hasSalePrice = isValidPriceCents(deal.salePriceCents);
  const hasOriginalPrice = isValidPriceCents(deal.originalPriceCents);
  const visiblePrice = hasSalePrice
    ? deal.salePriceCents
    : isValidPriceCents(deal.priceCents)
      ? deal.priceCents
      : undefined;

  const showOriginalStrikethrough =
    hasOriginalPrice && visiblePrice != null && deal.originalPriceCents > visiblePrice;
  const showDiscountBadge =
    typeof deal.discountPercent === "number" && deal.discountPercent > 0;
  const hasImage = typeof deal.imageUrl === "string" && deal.imageUrl.trim().length > 0;
  const shouldShowImage = hasImage && !imageFailed;
  const hasDescription =
    typeof deal.description === "string" && deal.description.trim().length > 0;

  return (
    <article className="flex flex-col gap-2 rounded-xl border border-black/10 bg-white p-4 shadow-sm">
      <div className="overflow-hidden rounded-lg border border-black/10 bg-black/5">
        {shouldShowImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={deal.imageUrl}
            alt={deal.title}
            loading="lazy"
            onError={() => setImageFailed(true)}
            className="h-40 w-full object-cover"
          />
        ) : (
          <div className="flex h-40 w-full items-center justify-center text-xs text-black/50">
            No image available
          </div>
        )}
      </div>

      <div className="flex items-start justify-between gap-3">
        <h2 className="text-base font-semibold leading-tight">
          <Link href={`/deals/${deal.slug}`} className="hover:underline">
            {deal.title}
          </Link>
        </h2>
        {showDiscountBadge ? (
          <div className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-800">
            -{deal.discountPercent}%
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {visiblePrice != null ? (
          <div className="whitespace-nowrap text-xl font-bold text-black">
            {formatPriceCents(visiblePrice)}
          </div>
        ) : (
          <div className="whitespace-nowrap text-sm font-medium text-black/60">
            Price unavailable
          </div>
        )}

        {showOriginalStrikethrough ? (
          <div className="whitespace-nowrap text-sm text-black/50 line-through">
            {formatPriceCents(deal.originalPriceCents)}
          </div>
        ) : null}
      </div>

      {hasDescription ? (
        <p
          className="text-sm text-black/70"
          style={{
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {deal.description}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-black/70">
        {deal.brand ? <span>Brand: {deal.brand}</span> : null}
        {deal.category ? <span>Category: {deal.category}</span> : null}
        {deal.size ? <span>Size: {deal.size}</span> : null}
      </div>

      <div className="pt-1">
        <Link
          href={`/deals/${deal.slug}`}
          className="inline-flex items-center justify-center rounded-lg bg-black px-3 py-2 text-sm font-semibold text-white hover:bg-black/90"
        >
          View deal details
        </Link>
      </div>
    </article>
  );
}


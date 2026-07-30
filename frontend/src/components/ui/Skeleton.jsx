export default function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded-2xl bg-gray-200 dark:bg-slate-800 ${className}`} />;
}

export function SkeletonGrid({ count = 4, itemClassName = "h-28" }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {[...Array(count)].map((_, i) => (
        <Skeleton key={i} className={itemClassName} />
      ))}
    </div>
  );
}

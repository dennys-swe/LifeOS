export default function EmptyState({ children, className = "" }) {
  return (
    <div className={`flex h-32 items-center justify-center text-sm text-gray-400 dark:text-slate-500 ${className}`}>
      {children}
    </div>
  );
}

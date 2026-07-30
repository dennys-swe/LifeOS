export default function CategoryDot({ color, className = "h-2.5 w-2.5" }) {
  return <span className={`flex-shrink-0 rounded-full ${className}`} style={{ backgroundColor: color }} />;
}

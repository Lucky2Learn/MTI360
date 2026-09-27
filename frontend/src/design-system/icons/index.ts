// MTI 360 icon set (T00-07, decision D3; DESIGN-SYSTEM.md §36): one coherent
// family — Lucide — re-exported under stable names. This is the ONLY module that
// may import "lucide-react" (enforced by tokens/guard.test.ts), so the family can
// be swapped or extended in one place. Add icons here when a component needs
// them; keep maritime references subtle (Compass, Anchor).
//
// Lucide icons render aria-hidden="true" unless given an accessible label.
// Decorative icons must stay hidden; meaning is always carried by text.

export type {
  LucideIcon as IconComponent,
  LucideProps as IconProps,
} from "lucide-react";

export {
  Anchor as AnchorIcon,
  ArrowDownRight as TrendDownIcon,
  ArrowLeft as BackIcon,
  ArrowRight as ForwardIcon,
  ArrowUpRight as TrendUpIcon,
  Calendar as CalendarIcon,
  Check as CheckIcon,
  ChevronDown as ChevronDownIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  CircleAlert as ErrorIcon,
  CircleCheck as SuccessIcon,
  CircleDot as TimelineDotIcon,
  Clock as ClockIcon,
  Compass as CompassIcon,
  Copy as CopyIcon,
  Download as DownloadIcon,
  Eye as ViewIcon,
  FileText as FileIcon,
  Inbox as EmptyIcon,
  Info as InfoIcon,
  LifeBuoy as SupportIcon,
  LoaderCircle as SpinnerIcon,
  LockKeyhole as LockIcon,
  Menu as MenuIcon,
  Minus as IndeterminateIcon,
  Ellipsis as MoreIcon,
  Pencil as EditIcon,
  Minus as TrendFlatIcon,
  Plus as AddIcon,
  RotateCw as RetryIcon,
  Settings as SettingsIcon,
  Sparkles as AiIcon,
  Trash2 as DeleteIcon,
  TriangleAlert as WarningIcon,
  Upload as UploadIcon,
  X as CloseIcon,
} from "lucide-react";

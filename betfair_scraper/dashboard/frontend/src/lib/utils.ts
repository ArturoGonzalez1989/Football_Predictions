import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTimeAgo(seconds: number | null | undefined): string {
  if (seconds == null) return "N/A"
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}

export function formatTimeTo(isoDate: string | null): string {
  if (!isoDate) return "N/A"
  const target = new Date(isoDate)
  const now = new Date()
  const diff = target.getTime() - now.getTime()
  const time = target.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  if (diff <= 0) return "Now"
  const hours = Math.floor(diff / 3600000)
  const mins = Math.floor((diff % 3600000) / 60000)
  if (hours > 0) return `in ${hours}h ${mins}m at ${time}`
  return `in ${mins}m at ${time}`
}

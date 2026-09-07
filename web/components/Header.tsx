"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles, Settings, User, Briefcase, ClipboardList } from "lucide-react";

const NAV = [
  { href: "/", label: "Dashboard", icon: ClipboardList },
  { href: "/profile", label: "Profile", icon: User },
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/onboarding", label: "Onboarding", icon: Sparkles },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Header() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 bg-[#0F1115] border-b border-[#1F2937]">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between gap-6">
        <div className="flex items-center gap-1 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center mr-3">
            <Sparkles size={18} className="text-white" />
          </div>
          <span className="text-base font-bold text-white tracking-tight">CareerOps AI</span>
        </div>

        <nav className="flex items-center gap-1">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 rounded-xl text-sm font-medium inline-flex items-center gap-1.5 transition-colors ${
                  active
                    ? "bg-blue-600 text-white"
                    : "text-gray-400 hover:text-white hover:bg-[#1A1D23]"
                }`}
              >
                <Icon size={14} />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="hidden md:flex items-center gap-2 shrink-0">
          <span className="text-xs text-gray-500">Gemini 2.5 Flash</span>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        </div>
      </div>
    </header>
  );
}

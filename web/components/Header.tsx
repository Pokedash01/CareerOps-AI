import Link from "next/link";

export default function Header() {
  return (
    <header className="bg-navy-900 text-white">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-1">
          <span className="text-lg mr-4 font-bold tracking-tight">CareerOps</span>
          <nav className="flex items-center gap-1 text-sm">
            <NavLink href="/">Dashboard</NavLink>
            <NavLink href="/profile">Profile</NavLink>
            <NavLink href="/jobs">Jobs</NavLink>
            <NavLink href="/onboarding">Onboarding</NavLink>
          </nav>
        </div>
        <span className="text-xs text-navy-400">Pipeline runs every 4h</span>
      </div>
    </header>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-3 py-1.5 rounded-md text-navy-200 hover:bg-navy-800 hover:text-white transition-colors text-sm"
    >
      {children}
    </Link>
  );
}

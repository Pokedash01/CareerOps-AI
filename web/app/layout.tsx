import type { Metadata } from "next";
import "./globals.css";
import PasswordGate from "@/components/PasswordGate";

export const metadata: Metadata = {
  title: "CareerOps Dashboard",
  description: "Your job-matching pipeline at a glance",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-navy-50 min-h-screen">
        <PasswordGate>{children}</PasswordGate>
      </body>
    </html>
  );
}

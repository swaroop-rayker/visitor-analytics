import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Visitor Analytics", template: "%s | Visitor Analytics" },
  description: "Privacy-preserving visitor analytics",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}


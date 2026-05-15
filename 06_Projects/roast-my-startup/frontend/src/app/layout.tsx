import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Roast My Startup - Brutally Honest AI Feedback",
  description: "Paste your startup URL and get roasted by a VC, engineer, customer, designer, and growth marketer. Funny enough to share. Useful enough to fix.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}

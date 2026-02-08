import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import AppNav from "@/components/AppNav";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SupportMind",
  description: "Self-learning AI support intelligence layer.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="h-full bg-background text-foreground selection:bg-primary selection:text-primary-foreground">
        <div className="flex h-full w-full bg-secondary/30 p-4 gap-4 md:p-6 md:gap-6">
          <AppNav />
          <div className="flex-1 flex h-full overflow-hidden">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}

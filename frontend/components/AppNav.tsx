"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", icon: MessageSquare, label: "Support Dashboard" },
  { href: "/review", icon: BookOpen, label: "Learning Review" },
];

export default function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="w-14 h-full flex flex-col items-center py-4 gap-2 bg-background/50 backdrop-blur-xl border border-border rounded-lg shadow-sm flex-shrink-0">
      {navItems.map(({ href, icon: Icon, label }) => {
        const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            title={label}
            className={cn(
              "w-10 h-10 flex items-center justify-center rounded-md transition-colors",
              isActive
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            )}
          >
            <Icon className="h-5 w-5" />
          </Link>
        );
      })}
    </nav>
  );
}

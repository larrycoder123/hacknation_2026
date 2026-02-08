"use client";

import { LearningEventDetail, ReviewStatus } from "@/app/types";
import { cn } from "@/lib/utils";
import { BookOpen } from "lucide-react";

interface LearningEventListProps {
  events: LearningEventDetail[];
  selectedEventId: string | null;
  onSelectEvent: (id: string) => void;
  statusFilter: ReviewStatus;
  onStatusFilterChange: (status: ReviewStatus) => void;
  isLoading: boolean;
}

const statusTabs: { value: ReviewStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

function formatRelativeTime(timestamp: string | undefined): string {
  if (!timestamp) return "";
  const diff = Date.now() - new Date(timestamp).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function LearningEventList({
  events,
  selectedEventId,
  onSelectEvent,
  statusFilter,
  onStatusFilterChange,
  isLoading,
}: LearningEventListProps) {
  return (
    <div className="w-80 h-full flex flex-col bg-background/50 backdrop-blur-xl flex-shrink-0 border border-border rounded-lg shadow-sm overflow-hidden">
      <div className="p-4 border-b border-border/50 space-y-3 bg-background/50">
        <div className="flex items-center gap-2">
          <div className="bg-primary/10 p-1 rounded-md border border-primary/20">
            <BookOpen className="h-3.5 w-3.5 text-primary" />
          </div>
          <h2 className="text-sm font-semibold text-foreground tracking-tight">Learning Review</h2>
          <div className="ml-auto text-xs text-muted-foreground font-medium bg-secondary px-2 py-0.5 rounded-md tabular-nums">
            {events.length}
          </div>
        </div>

        <div className="flex gap-1 bg-secondary/50 p-0.5 rounded-md">
          {statusTabs.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => onStatusFilterChange(value)}
              className={cn(
                "flex-1 text-xs font-medium py-1.5 rounded transition-colors",
                statusFilter === value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {isLoading ? (
          <p className="text-sm text-muted-foreground text-center py-8">Loading...</p>
        ) : events.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">No events found</p>
        ) : (
          events.map((event) => (
            <button
              key={event.event_id}
              onClick={() => onSelectEvent(event.event_id)}
              className={cn(
                "w-full text-left p-3 rounded-md border border-transparent transition-all duration-200 group",
                selectedEventId === event.event_id
                  ? "bg-background shadow-sm border-border"
                  : "hover:bg-muted/50 hover:border-border/20 text-muted-foreground hover:text-foreground"
              )}
            >
              <div className="flex justify-end mb-1.5">
                <span className="text-[10px] font-medium opacity-50 tabular-nums">
                  {formatRelativeTime(event.event_timestamp)}
                </span>
              </div>
              <div className={cn(
                "font-medium text-sm truncate mb-0.5 tracking-tight",
                selectedEventId === event.event_id ? "text-foreground" : "text-foreground/80 group-hover:text-foreground"
              )}>
                {event.draft_summary}
              </div>
              <div className="text-xs truncate opacity-70">{event.trigger_ticket_number}</div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

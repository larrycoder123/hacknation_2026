"use client";

import { useState } from "react";
import {
  LearningEventDetail as LearningEventDetailType,
  ReviewDecisionPayload,
  FinalStatus,
} from "@/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { BookOpen } from "lucide-react";

interface LearningEventDetailProps {
  event: LearningEventDetailType | null;
  onReview: (eventId: string, payload: ReviewDecisionPayload) => Promise<void>;
  isReviewing: boolean;
}

/**
 * LearningEventDetail Component
 * 
 * Displays detailed information about a learning event, including the conversation content,
 * recommended actions, and potential knowledge gaps.
 */
export default function LearningEventDetail({
  event,
  onReview,
  isReviewing,
}: LearningEventDetailProps) {
  const [reason, setReason] = useState("");

  if (!event) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background/50 backdrop-blur-xl border border-border rounded-lg shadow-sm">
        <div className="text-center text-muted-foreground">
          <BookOpen className="h-12 w-12 mx-auto mb-3 opacity-20" />
          <p className="text-sm">Select an event to review</p>
        </div>
      </div>
    );
  }

  const isPending = !event.final_status;

  const handleReview = async (decision: FinalStatus) => {
    await onReview(event.event_id, {
      decision,
      reviewer_role: "Tier 3 Support",
      reason: reason || undefined,
    });
    setReason("");
  };

  return (
    <div className="flex-1 flex flex-col bg-background/50 backdrop-blur-xl border border-border rounded-lg shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-border/50 bg-background/50">
        <code className="text-xs font-mono text-muted-foreground mb-2 block">
          {event.event_id}
        </code>
        <h2 className="text-base font-semibold tracking-tight">{event.draft_summary}</h2>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Detected Gap */}
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Detected Gap</h3>
          <div className="bg-muted/30 border border-border/50 rounded-md p-3 text-sm whitespace-pre-wrap">
            {event.detected_gap}
          </div>
        </div>

        {/* Source Ticket */}
        {(event.trigger_ticket_subject || event.trigger_ticket_description) && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Source Ticket</h3>
            <div className="bg-muted/30 border border-border/50 rounded-md p-3 text-sm space-y-2">
              <p><span className="text-muted-foreground">Ticket:</span> <span className="font-mono text-xs">{event.trigger_ticket_number}</span></p>
              {event.trigger_ticket_subject && <p><span className="text-muted-foreground">Subject:</span> {event.trigger_ticket_subject}</p>}
              {event.trigger_ticket_description && <p className="whitespace-pre-wrap text-foreground/80">{event.trigger_ticket_description}</p>}
              {event.trigger_ticket_resolution && (
                <div>
                  <span className="text-muted-foreground">Resolution:</span>
                  <p className="whitespace-pre-wrap text-foreground/80 mt-1">{event.trigger_ticket_resolution}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Proposed KB Article */}
        {event.proposed_article && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Proposed KB Article</h3>
            <div className="bg-muted/30 border border-border/50 rounded-md p-3 text-sm space-y-2">
              <h4 className="font-semibold">{event.proposed_article.title}</h4>
              <p className="whitespace-pre-wrap text-foreground/80 leading-relaxed">{event.proposed_article.body}</p>
              {event.proposed_article.tags && <p className="text-xs text-muted-foreground">Tags: {event.proposed_article.tags}</p>}
            </div>
          </div>
        )}

        {/* Flagged Article (CONTRADICTION only) */}
        {event.event_type === "CONTRADICTION" && event.flagged_article && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Flagged Article (Existing)</h3>
            <div className="bg-muted/30 border border-border/50 rounded-md p-3 text-sm space-y-2">
              <h4 className="font-semibold">{event.flagged_article.title}</h4>
              <p className="whitespace-pre-wrap text-foreground/80 leading-relaxed">{event.flagged_article.body}</p>
            </div>
          </div>
        )}

        {/* Review Actions */}
        {isPending ? (
          <div className="space-y-3 pt-2 border-t border-border/50">
            <Textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Reason (optional)"
              className="min-h-[60px] text-sm"
            />
            <div className="flex gap-2">
              <Button
                onClick={() => handleReview("Approved")}
                disabled={isReviewing}
                className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                Approve
              </Button>
              <Button
                onClick={() => handleReview("Rejected")}
                disabled={isReviewing}
                variant="destructive"
                className="flex-1"
              >
                Reject
              </Button>
            </div>
          </div>
        ) : (
          <div className="pt-2 border-t border-border/50 text-sm text-muted-foreground">
            <span className={event.final_status === "Approved" ? "text-emerald-400" : "text-red-400"}>
              {event.final_status}
            </span>
            {event.reviewer_role && <span> by {event.reviewer_role}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

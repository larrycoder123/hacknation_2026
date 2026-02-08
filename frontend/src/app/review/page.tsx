"use client";

import { useState, useEffect, useCallback } from "react";
import {
  LearningEventDetail as LearningEventDetailType,
  ReviewStatus,
  ReviewDecisionPayload,
} from "@/types";
import LearningEventList from "@/components/LearningEventList";
import LearningEventDetailComponent from "@/components/LearningEventDetail";
import { fetchLearningEvents, reviewLearningEvent } from "../api/client";

export default function ReviewPage() {
  const [events, setEvents] = useState<LearningEventDetailType[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ReviewStatus>("pending");
  const [isLoading, setIsLoading] = useState(true);
  const [isReviewing, setIsReviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedEvent = events.find((e) => e.event_id === selectedEventId) || null;

  const loadEvents = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchLearningEvents({ status: statusFilter });
      setEvents(result.events);
    } catch (err) {
      console.error("Failed to fetch learning events:", err);
      setError("Failed to load learning events.");
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const handleReview = async (eventId: string, payload: ReviewDecisionPayload) => {
    setIsReviewing(true);
    try {
      await reviewLearningEvent(eventId, payload);
      await loadEvents();
      setSelectedEventId(null);
    } catch (err) {
      console.error("Failed to review event:", err);
      setError("Failed to submit review.");
    } finally {
      setIsReviewing(false);
    }
  };

  return (
    <div className="flex h-full w-full text-foreground overflow-hidden font-sans antialiased selection:bg-primary/20 relative gap-4 md:gap-6">
      {error && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 bg-destructive/90 text-white px-4 py-2 text-sm flex items-center gap-4 rounded-full shadow-lg backdrop-blur-md animate-in fade-in slide-in-from-top-4">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="font-bold hover:opacity-80">X</button>
        </div>
      )}

      <LearningEventList
        events={events}
        selectedEventId={selectedEventId}
        onSelectEvent={setSelectedEventId}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        isLoading={isLoading}
      />

      <LearningEventDetailComponent
        event={selectedEvent}
        onReview={handleReview}
        isReviewing={isReviewing}
      />
    </div>
  );
}

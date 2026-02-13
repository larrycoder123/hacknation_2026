/**
 * Shared TypeScript interfaces matching the backend Pydantic schemas.
 *
 * All field names use snake_case to match the JSON returned by the FastAPI
 * backend. The ConversationDisplay interface provides a camelCase variant
 * for use in React components (converted via toConversationDisplay).
 */

export type Priority = 'High' | 'Medium' | 'Low';
export type ConversationStatus = 'Open' | 'Pending' | 'Resolved' | 'Closed';

export interface Conversation {
  id: string;
  customer_name: string;  // snake_case to match backend
  subject: string;
  priority: Priority;
  status: ConversationStatus;
  time_ago: string;
  avatar_url?: string;
  last_message?: string;
}

// Frontend-friendly version with camelCase (for display)
export interface ConversationDisplay {
  id: string;
  customerName: string;
  subject: string;
  priority: Priority;
  status: ConversationStatus;
  timeAgo: string;
  avatarUrl?: string;
  lastMessage?: string;
}

export type Sender = 'agent' | 'customer' | 'system';

export interface Message {
  id: string;
  conversation_id: string;  // snake_case to match backend
  sender: Sender;
  content: string;
  timestamp: string; // ISO string or formatted time
}

export type ActionType = 'script' | 'response' | 'action';

export interface ScoreBreakdown {
  vector_similarity: number;
  rerank_score: number | null;
  confidence: number;
  usage_count: number;
  freshness: number;
  learning_score: number;
  final_score: number;
}

export interface SuggestedAction {
  id: string;
  type: ActionType;
  confidence_score: number;
  title: string;
  description: string;
  content: string;
  source: string;
  adapted_summary?: string;
  score_breakdown?: ScoreBreakdown;
}

export interface CloseConversationPayload {
  conversation_id: string;
  resolution_type: 'Resolved Successfully' | 'Not Applicable';
  notes?: string;
  create_ticket: boolean;
}

export interface Ticket {
  ticket_number?: string;
  subject: string;
  description: string;
  resolution: string;
  tags: string[];
  category?: string;
  related_error_codes?: string[];
  steps_to_reproduce?: string;
  resolution_steps?: string[];
  internal_notes?: string;
}

export interface ConfidenceUpdate {
  source_type: string;
  source_id: string;
  delta: number;
  new_confidence: number;
  new_usage_count: number;
}

export type GapClassification = 'SAME_KNOWLEDGE' | 'CONTRADICTS' | 'NEW_KNOWLEDGE';

export interface SelfLearningResult {
  ticket_number: string;
  retrieval_logs_processed: number;
  confidence_updates: ConfidenceUpdate[];
  gap_classification?: GapClassification;
  matched_kb_article_id?: string;
  match_similarity?: number;
  learning_event_id?: string;
  drafted_kb_article_id?: string;
}

export interface CloseConversationResponse {
  status: string;
  message: string;
  ticket?: Ticket;
  warnings: string[];
  learning_result?: SelfLearningResult;
}

// ── Learning review types ─────────────────────────────────────────

export type EventType = 'GAP' | 'CONTRADICTION' | 'CONFIRMED';
export type ReviewStatus = 'pending' | 'approved' | 'rejected';
export type ReviewerRole = 'Tier 3 Support' | 'Support Ops Review';
export type FinalStatus = 'Approved' | 'Rejected';

export interface KBArticleSummary {
  kb_article_id: string;
  title: string;
  body: string;
  tags?: string;
  module?: string;
  category?: string;
  status?: string;
}

export interface LearningEventDetail {
  event_id: string;
  trigger_ticket_number: string;
  detected_gap: string;
  event_type: EventType;
  proposed_kb_article_id?: string;
  flagged_kb_article_id?: string;
  draft_summary: string;
  final_status?: FinalStatus;
  reviewer_role?: string;
  event_timestamp?: string;
  proposed_article?: KBArticleSummary;
  flagged_article?: KBArticleSummary;
  trigger_ticket_subject?: string;
  trigger_ticket_description?: string;
  trigger_ticket_resolution?: string;
}

export interface LearningEventListResponse {
  events: LearningEventDetail[];
  total_count: number;
}

export interface ReviewDecisionPayload {
  decision: FinalStatus;
  reviewer_role: ReviewerRole;
  reason?: string;
}

export interface SimulateCustomerResponse {
  content: string;
  resolved: boolean;
}

// Utility function to convert backend conversation to display format
export function toConversationDisplay(conversation: Conversation): ConversationDisplay {
  return {
    id: conversation.id,
    customerName: conversation.customer_name,
    subject: conversation.subject,
    priority: conversation.priority,
    status: conversation.status,
    timeAgo: conversation.time_ago,
    avatarUrl: conversation.avatar_url,
    lastMessage: conversation.last_message,
  };
}

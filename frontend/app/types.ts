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

export interface SuggestedAction {
  id: string;
  type: ActionType;
  confidence_score: number;
  title: string;
  description: string;
  content: string;
  source: string;
}

export interface CloseConversationPayload {
  conversation_id: string;
  resolution_type: 'Resolved Successfully' | 'Not Applicable';
  notes?: string;
  create_ticket: boolean;
}

export interface Ticket {
  subject: string;
  description: string;
  resolution: string;
  tags: string[];
  category?: string;
  related_error_codes?: string[];
  steps_to_reproduce?: string;
  resolution_steps?: string[];
  customer_communication_template?: string;
  internal_notes?: string;
}

export interface CloseConversationResponse {
  status: string;
  message: string;
  ticket?: Ticket;
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

export type Priority = 'High' | 'Medium' | 'Low';
export type TicketStatus = 'Open' | 'Pending' | 'Resolved' | 'Closed';

export interface Ticket {
  id: string;
  customer_name: string;  // Changed to snake_case to match backend
  subject: string;
  priority: Priority;
  status: TicketStatus;
  time_ago: string;
  avatar_url?: string;
  last_message?: string;
}

// Frontend-friendly version with camelCase (for display)
export interface TicketDisplay {
  id: string;
  customerName: string;
  subject: string;
  priority: Priority;
  status: TicketStatus;
  timeAgo: string;
  avatarUrl?: string;
  lastMessage?: string;
}

export type Sender = 'agent' | 'customer' | 'system';

export interface Message {
  id: string;
  ticket_id: string;  // Changed to snake_case to match backend
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

export interface CloseTicketPayload {
  ticket_id: string;
  resolution_type: 'Resolved Successfully' | 'Not Applicable';
  notes?: string;
  add_to_knowledge_base: boolean;
}

export interface KnowledgeArticle {
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

export interface CloseTicketResponse {
  status: string;
  message: string;
  knowledge_article?: KnowledgeArticle;
}

// Utility function to convert backend ticket to display format
export function toTicketDisplay(ticket: Ticket): TicketDisplay {
  return {
    id: ticket.id,
    customerName: ticket.customer_name,
    subject: ticket.subject,
    priority: ticket.priority,
    status: ticket.status,
    timeAgo: ticket.time_ago,
    avatarUrl: ticket.avatar_url,
    lastMessage: ticket.last_message,
  };
}

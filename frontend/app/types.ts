export type Priority = 'High' | 'Medium' | 'Low';
export type TicketStatus = 'Open' | 'Pending' | 'Resolved' | 'Closed';

export interface Ticket {
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
  ticketId: string;
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

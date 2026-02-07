import { Ticket, Priority } from '../app/types';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';

interface TicketQueueProps {
    tickets: Ticket[];
    selectedTicketId: string | null;
    onSelectTicket: (id: string) => void;
}

const PriorityBadge = ({ priority }: { priority: Priority }) => {
    const variants: Record<Priority, string> = {
        High: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-200/20',
        Medium: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-200/20',
        Low: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200/20',
    };

    return (
        <span className={cn("px-2 py-0.5 rounded-md text-xs uppercase tracking-wider font-semibold border", variants[priority])}>
            {priority}
        </span>
    );
};

export default function TicketQueue({ tickets, selectedTicketId, onSelectTicket }: TicketQueueProps) {
    const [searchQuery, setSearchQuery] = useState('');

    const filteredTickets = tickets.filter(ticket =>
        ticket.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ticket.customerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ticket.id.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="w-80 border-r border-border h-full flex flex-col bg-muted/10 backdrop-blur-xl flex-shrink-0">
            <div className="p-4 border-b border-border space-y-4">
                <div className="flex items-center justify-between">
                    <h2 className="text-base font-semibold text-foreground tracking-tight">Inbox</h2>
                    <div className="text-sm text-muted-foreground font-medium bg-secondary px-2 py-0.5 rounded-md">
                        {filteredTickets.length}
                    </div>
                </div>
                <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search tickets..."
                        className="pl-8 bg-background border-border"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {filteredTickets.map((ticket) => (
                    <button
                        key={ticket.id}
                        onClick={() => onSelectTicket(ticket.id)}
                        className={cn(
                            "w-full text-left p-3 rounded-lg border border-transparent transition-all duration-200 group relative",
                            selectedTicketId === ticket.id
                                ? "bg-background shadow-sm border-border"
                                : "hover:bg-sidebar-accent hover:border-border/50 text-muted-foreground hover:text-foreground"
                        )}
                    >
                        <div className="flex justify-between items-start mb-2">
                            <PriorityBadge priority={ticket.priority} />
                            <span className="text-xs font-medium opacity-60 tabular-nums">{ticket.timeAgo}</span>
                        </div>
                        <div className={cn(
                            "font-medium text-base truncate mb-0.5",
                            selectedTicketId === ticket.id ? "text-foreground" : "text-foreground/80 group-hover:text-foreground"
                        )}>
                            {ticket.customerName}
                        </div>
                        <div className="text-sm truncate opacity-70">
                            {ticket.subject}
                        </div>
                    </button>
                ))}
            </div>
        </div>
    );
}

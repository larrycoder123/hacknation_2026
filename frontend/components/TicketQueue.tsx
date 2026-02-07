import { Ticket, Priority } from '../app/types';

interface TicketQueueProps {
    tickets: Ticket[];
    selectedTicketId: string | null;
    onSelectTicket: (id: string) => void;
}

const PriorityBadge = ({ priority }: { priority: Priority }) => {
    const colors = {
        High: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
        Medium: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
        Low: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    };

    return (
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[priority]}`}>
            {priority}
        </span>
    );
};

export default function TicketQueue({ tickets, selectedTicketId, onSelectTicket }: TicketQueueProps) {
    return (
        <div className="w-80 border-r border-zinc-200 dark:border-zinc-800 h-full flex flex-col bg-white dark:bg-zinc-950 flex-shrink-0">
            <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
                <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Ticket Queue</h2>
            </div>
            <div className="flex-1 overflow-y-auto">
                {tickets.map((ticket) => (
                    <button
                        key={ticket.id}
                        onClick={() => onSelectTicket(ticket.id)}
                        className={`w-full text-left p-4 border-b border-zinc-100 dark:border-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-900/50 transition-colors ${selectedTicketId === ticket.id ? 'bg-blue-50 dark:bg-blue-900/10 border-l-4 border-l-blue-500' : 'border-l-4 border-l-transparent'
                            }`}
                    >
                        <div className="flex justify-between items-start mb-1">
                            <PriorityBadge priority={ticket.priority} />
                            <span className="text-xs text-zinc-500 dark:text-zinc-400">{ticket.timeAgo}</span>
                        </div>
                        <div className="font-medium text-zinc-900 dark:text-zinc-100 truncate mb-1">
                            {ticket.customerName}
                        </div>
                        <div className="text-sm text-zinc-600 dark:text-zinc-400 truncate">
                            {ticket.subject}
                        </div>
                    </button>
                ))}
            </div>
        </div>
    );
}

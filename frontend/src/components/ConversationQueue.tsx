"use client";

import { ConversationDisplay, Priority } from '@/types';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Search, Zap, CheckCircle2 } from 'lucide-react';

interface ConversationQueueProps {
    conversations: ConversationDisplay[];
    selectedConversationId: string | null;
    onSelectConversation: (id: string) => void;
}

const PriorityBadge = ({ priority }: { priority: Priority }) => {
    const variants: Record<Priority, string> = {
        High: 'bg-red-500/10 text-red-400 border-red-500/20',
        Medium: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
        Low: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    };

    return (
        <span className={cn("px-2 py-0.5 rounded-md text-[10px] uppercase tracking-wider font-semibold border", variants[priority])}>
            {priority}
        </span>
    );
};

/**
 * ConversationQueue Component
 * 
 * Displays a list of active conversations with search and filtering capabilities.
 * Allows selecting a conversation to view its details.
 */
export default function ConversationQueue({ conversations, selectedConversationId, onSelectConversation }: ConversationQueueProps) {
    const [searchQuery, setSearchQuery] = useState('');

    const parseTimeAgo = (t: string): number => {
        const match = t.match(/^(\d+)(m|h|d)$/);
        if (!match) return 9999;
        const [, val, unit] = match;
        const multiplier = unit === 'm' ? 1 : unit === 'h' ? 60 : 1440;
        return parseInt(val) * multiplier;
    };

    const filteredConversations = conversations
        .filter(conversation =>
            conversation.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
            conversation.customerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
            conversation.id.toLowerCase().includes(searchQuery.toLowerCase())
        )
        .sort((a, b) => {
            const aResolved = a.status === 'Resolved' ? 1 : 0;
            const bResolved = b.status === 'Resolved' ? 1 : 0;
            if (aResolved !== bResolved) return aResolved - bResolved;
            return parseTimeAgo(a.timeAgo) - parseTimeAgo(b.timeAgo);
        });

    return (
        <div className="w-80 h-full flex flex-col bg-background/50 backdrop-blur-xl flex-shrink-0 border border-border rounded-lg shadow-sm overflow-hidden">
            <div className="p-4 border-b border-border/50 space-y-4 bg-background/50">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="bg-primary/10 p-1 rounded-md border border-primary/20">
                            <Zap className="h-3.5 w-3.5 text-primary fill-primary/20" />
                        </div>
                        <h2 className="text-sm font-semibold text-foreground tracking-tight">Inbox</h2>
                    </div>
                    <div className="text-xs text-muted-foreground font-medium bg-secondary px-2 py-0.5 rounded-md tabular-nums">
                        {filteredConversations.length}
                    </div>
                </div>
                <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                    <Input
                        placeholder="Search..."
                        className="pl-8 h-9 text-sm bg-background/50 border-border/50 transition-colors focus-visible:ring-1"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {filteredConversations.map((conversation, idx) => {
                    const isResolved = conversation.status === 'Resolved';
                    const isFirstResolved = isResolved && (idx === 0 || filteredConversations[idx - 1].status !== 'Resolved');

                    return (
                        <div key={conversation.id}>
                            {isFirstResolved && (
                                <div className="flex items-center gap-2 px-3 pt-3 pb-1">
                                    <div className="flex-1 border-t border-border/40" />
                                    <span className="text-[9px] font-semibold text-muted-foreground/50 uppercase tracking-widest">Resolved</span>
                                    <div className="flex-1 border-t border-border/40" />
                                </div>
                            )}
                            <button
                                onClick={() => onSelectConversation(conversation.id)}
                                className={cn(
                                    "w-full text-left p-3 rounded-md border border-transparent transition-all duration-200 group relative",
                                    selectedConversationId === conversation.id
                                        ? "bg-background shadow-sm border-border"
                                        : "hover:bg-muted/50 hover:border-border/20 text-muted-foreground hover:text-foreground",
                                    isResolved && selectedConversationId !== conversation.id && "opacity-50"
                                )}
                            >
                                <div className="flex justify-between items-start mb-1.5">
                                    {isResolved ? (
                                        <span className="px-2 py-0.5 rounded-md text-[10px] uppercase tracking-wider font-semibold border bg-emerald-500/10 text-emerald-400 border-emerald-500/20 flex items-center gap-1">
                                            <CheckCircle2 className="w-2.5 h-2.5" />
                                            Resolved
                                        </span>
                                    ) : (
                                        <PriorityBadge priority={conversation.priority} />
                                    )}
                                    <span className="text-[10px] font-medium opacity-50 tabular-nums">{conversation.timeAgo}</span>
                                </div>
                                <div className={cn(
                                    "font-medium text-sm truncate mb-0.5 tracking-tight",
                                    selectedConversationId === conversation.id ? "text-foreground" : "text-foreground/80 group-hover:text-foreground"
                                )}>
                                    {conversation.customerName}
                                </div>
                                <div className="text-xs truncate opacity-70">
                                    {conversation.subject}
                                </div>
                            </button>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

import { Ticket, Message } from '../app/types';
import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Avatar } from '@/components/ui/avatar';
import { cn } from '@/lib/utils';
import { Send, X, MoreHorizontal, Paperclip } from 'lucide-react';

interface TicketDetailProps {
    ticket: Ticket | null;
    messages: Message[];
    onSendMessage: (content: string) => void;
    onCloseTicket: () => void;
    inputMessage?: string;
    onInputChange?: (value: string) => void;
}

export default function TicketDetail({ ticket, messages, onSendMessage, onCloseTicket, inputMessage, onInputChange }: TicketDetailProps) {
    const [internalInput, setInternalInput] = useState('');
    const inputValue = inputMessage !== undefined ? inputMessage : internalInput;
    const setInputValue = onInputChange || setInternalInput;
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = () => {
        if (inputValue.trim()) {
            onSendMessage(inputValue);
            setInputValue('');
        }
    };

    if (!ticket) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-background text-muted-foreground gap-2">
                <div className="h-12 w-12 rounded-lg bg-muted/50 flex items-center justify-center">
                    <MoreHorizontal className="h-6 w-6 opacity-50" />
                </div>
                <p className="text-sm font-medium">Select a ticket to view details</p>
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col h-full bg-background relative">
            {/* Header */}
            <div className="h-16 border-b border-border flex items-center justify-between px-6 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
                <div className="flex items-center gap-4">
                    <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-muted-foreground">#{ticket.id}</span>
                            <h2 className="text-sm font-semibold text-foreground tracking-tight line-clamp-1">
                                {ticket.subject}
                            </h2>
                            <Badge variant="outline" className={cn(
                                "ml-2 text-[10px] uppercase tracking-wider h-5 px-1.5",
                                ticket.status === 'Open' ? "bg-emerald-500/10 text-emerald-600 border-emerald-200/20" : "bg-zinc-100 text-zinc-600"
                            )}>
                                {ticket.status}
                            </Badge>
                        </div>
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <span>via</span>
                            <span className="font-medium text-foreground">{ticket.customerName}</span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">

                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onCloseTicket}
                        className="h-8 text-xs gap-1.5 hidden sm:flex"
                    >
                        <X className="h-3.5 w-3.5" />
                        Close Ticket
                    </Button>
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {messages.map((message) => {
                    const isAgent = message.sender === 'agent';
                    return (
                        <div
                            key={message.id}
                            className={cn(
                                "flex gap-3 max-w-3xl",
                                isAgent ? "ml-auto flex-row-reverse" : ""
                            )}
                        >
                            <Avatar className="h-8 w-8 mt-0.5 border border-border">
                                {isAgent ? null : <div className="text-[10px]">{ticket.customerName.charAt(0)}</div>}
                            </Avatar>
                            <div className={cn(
                                "flex flex-col gap-1 min-w-0 max-w-[80%]",
                                isAgent ? "items-end" : "items-start"
                            )}>
                                <div className="flex items-center gap-2">
                                    <span className="text-[11px] font-medium text-foreground">
                                        {isAgent ? 'Support Agent' : ticket.customerName}
                                    </span>
                                    <span className="text-[10px] text-muted-foreground">{message.timestamp}</span>
                                </div>
                                <div
                                    className={cn(
                                        "rounded-md px-4 py-2.5 text-sm shadow-sm leading-relaxed",
                                        isAgent
                                            ? "bg-zinc-700 text-foreground"
                                            : "bg-muted text-foreground border border-border/50"
                                    )}
                                >
                                    <div className="whitespace-pre-wrap">{message.content}</div>
                                </div>
                            </div>
                        </div>
                    );
                })}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-border bg-background">
                <div className="relative flex flex-col gap-2 rounded-lg border border-border bg-muted/20 p-2 focus-within:ring-1 focus-within:ring-ring focus-within:border-ring transition-all">
                    <Textarea
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                        placeholder="Type your reply..."
                        className="min-h-[80px] w-full border-none bg-transparent shadow-none focus-visible:ring-0 p-2 resize-none text-sm placeholder:text-muted-foreground/50"
                    />
                    <div className="flex items-center justify-between px-2 pb-1">
                        <div className="flex items-center gap-1">
                            <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground">
                                <Paperclip className="h-3.5 w-3.5" />
                            </Button>
                        </div>
                        <Button
                            onClick={handleSend}
                            disabled={!inputValue.trim()}
                            size="sm"
                            className={cn(
                                "h-7 px-3 text-xs bg-primary hover:bg-primary/90 text-primary-foreground",
                                !inputValue.trim() && "opacity-50"
                            )}
                        >
                            Send Reply
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    );
}

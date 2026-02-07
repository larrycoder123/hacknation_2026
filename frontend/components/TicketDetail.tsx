import { Ticket, Message } from '../app/types';
import { useState, useRef, useEffect } from 'react';

interface TicketDetailProps {
    ticket: Ticket | null;
    messages: Message[];
    onSendMessage: (content: string) => void;
    onCloseTicket: () => void;
    inputMessage?: string;
    onInputChange?: (value: string) => void;
}

export default function TicketDetail({ ticket, messages, onSendMessage, onCloseTicket, inputMessage, onInputChange }: TicketDetailProps) {
    // Use internal state if props are not provided (backwards compatibility/flexibility)
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
            <div className="flex-1 flex items-center justify-center bg-zinc-50 dark:bg-zinc-900 text-zinc-500">
                Select a ticket to view details
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col h-full bg-white dark:bg-zinc-950 relative">
            {/* Header */}
            <div className="h-16 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between px-6 bg-white dark:bg-zinc-950 sticky top-0 z-10">
                <div>
                    <div className="flex items-center gap-3">
                        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                            #{ticket.id} - {ticket.subject}
                        </h2>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium 
              ${ticket.status === 'Open' ? 'bg-green-100 text-green-800 dark:bg-green-900/30' : 'bg-gray-100 text-gray-800'}
            `}>
                            {ticket.status}
                        </span>
                    </div>
                    <div className="text-sm text-zinc-500">
                        via {ticket.customerName}
                    </div>
                </div>
                <button
                    onClick={onCloseTicket}
                    className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 border border-zinc-300 dark:border-zinc-700 rounded-md hover:bg-zinc-50 dark:hover:bg-zinc-900 transition-colors"
                >
                    Close Ticket
                </button>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-zinc-50/50 dark:bg-zinc-900/20">
                {messages.map((message) => {
                    const isAgent = message.sender === 'agent';
                    return (
                        <div
                            key={message.id}
                            className={`flex ${isAgent ? 'justify-end' : 'justify-start'}`}
                        >
                            <div
                                className={`max-w-[70%] rounded-2xl px-4 py-3 shadow-sm ${isAgent
                                        ? 'bg-blue-600 text-white rounded-br-none'
                                        : 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 border border-zinc-200 dark:border-zinc-700 rounded-bl-none'
                                    }`}
                            >
                                <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                                <div className={`text-xs mt-1 ${isAgent ? 'text-blue-100' : 'text-zinc-400'}`}>
                                    {message.timestamp}
                                </div>
                            </div>
                        </div>
                    );
                })}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
                <div className="relative">
                    <textarea
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                        placeholder="Type your reply..."
                        className="w-full min-h-[100px] p-3 pr-24 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                    />
                    <div className="absolute bottom-3 right-3">
                        <button
                            onClick={handleSend}
                            disabled={!inputValue.trim()}
                            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            Send
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
